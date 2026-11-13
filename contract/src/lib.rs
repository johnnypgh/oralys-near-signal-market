//! Oralys Signal Market (NEAR hackathon build, Agent Economy track).
//!
//! A pay-per-signal escrow. A buyer agent attaches NEAR and opens a request
//! with a minimum quality score and a deadline. The registered Oralys signer
//! (an ed25519 key held off chain by the seller's oracle) signs a fulfillment
//! that names the request, the signal id, a keyed hash of the transcript and a
//! quality score from 0 to 100. The contract checks the signature on chain with
//! `env::ed25519_verify`, checks the score against the buyer's minimum, and pays
//! the registered seller account. If nothing valid arrives before the deadline,
//! anyone can trigger a refund to the buyer.
//!
//! The transcript itself never touches the chain. Only its keyed hash does.

use near_sdk::json_types::{U128, U64};
use near_sdk::serde::Serialize;
use near_sdk::serde_json::json;
use near_sdk::store::{IterableMap, LookupMap};
use near_sdk::{
    env, near, require, AccountId, BorshStorageKey, CurveType, NearToken, PanicOnDefault, Promise,
    PublicKey,
};

pub const EVENT_STANDARD: &str = "oralys_signal_market";
pub const EVENT_VERSION: &str = "1.0.0";
pub const SIGNING_DOMAIN: &str = "oralys-signal-v1";
pub const MAX_QUALITY: u8 = 100;
pub const MAX_SIGNAL_ID_LEN: usize = 64;
pub const MAX_TOPIC_LEN: usize = 128;
/// Longest allowed request window: 30 days.
pub const MAX_TTL_SECONDS: u64 = 30 * 24 * 60 * 60;
const NS_PER_SECOND: u64 = 1_000_000_000;

#[near(serializers = [borsh])]
#[derive(BorshStorageKey)]
enum StorageKey {
    Requests,
    Fulfillments,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub enum RequestStatus {
    Open,
    Fulfilled,
    Refunded,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug)]
pub struct SignalRequest {
    pub id: U64,
    pub buyer: AccountId,
    /// Escrowed budget in yoctoNEAR. Paid in full to the seller on a valid fulfillment.
    pub budget: U128,
    pub min_quality: u8,
    /// Free text describing what the buyer wants, for example a topic tag.
    pub topic: String,
    pub created_at_ns: U64,
    pub deadline_ns: U64,
    pub status: RequestStatus,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug)]
pub struct Fulfillment {
    pub request_id: U64,
    pub signal_id: String,
    /// Lowercase hex of a 32 byte keyed hash of the transcript.
    pub keyed_hash: String,
    pub quality_score: u8,
    pub seller: AccountId,
    pub paid: U128,
    pub submitted_by: AccountId,
    pub fulfilled_at_ns: U64,
}

#[near(serializers = [json])]
pub struct MarketConfig {
    pub owner: AccountId,
    pub seller: AccountId,
    pub signer_public_key: PublicKey,
    pub next_request_id: U64,
    pub signing_domain: String,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct SignalMarket {
    owner: AccountId,
    seller: AccountId,
    signer_public_key: PublicKey,
    next_request_id: u64,
    requests: IterableMap<u64, SignalRequest>,
    fulfillments: LookupMap<u64, Fulfillment>,
}

fn emit_event<T: Serialize>(event: &str, data: T) {
    let payload = json!({
        "standard": EVENT_STANDARD,
        "version": EVENT_VERSION,
        "event": event,
        "data": [data],
    });
    env::log_str(&format!("EVENT_JSON:{}", payload));
}

fn ed25519_bytes(pk: &PublicKey) -> [u8; 32] {
    require!(pk.curve_type() == CurveType::ED25519, "signer key must be ed25519");
    let raw = pk.as_bytes();
    // First byte is the curve tag, the remaining 32 are the key.
    require!(raw.len() == 33, "bad ed25519 key length");
    let mut out = [0u8; 32];
    out.copy_from_slice(&raw[1..]);
    out
}

fn is_lower_hex(s: &str) -> bool {
    s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn valid_signal_id(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= MAX_SIGNAL_ID_LEN
        && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

/// The exact bytes the Oralys signer signs. Binding the contract account id and
/// the request id stops a signature from being replayed on another request or
/// another deployment.
pub fn signing_message(
    contract_id: &str,
    request_id: u64,
    signal_id: &str,
    keyed_hash: &str,
    quality_score: u8,
) -> String {
    format!(
        "{}|{}|{}|{}|{}|{}",
        SIGNING_DOMAIN, contract_id, request_id, signal_id, keyed_hash, quality_score
    )
}

#[near]
impl SignalMarket {
    #[init]
    pub fn new(owner: AccountId, seller: AccountId, signer_public_key: PublicKey) -> Self {
        ed25519_bytes(&signer_public_key);
        Self {
            owner,
            seller,
            signer_public_key,
            next_request_id: 0,
            requests: IterableMap::new(StorageKey::Requests),
            fulfillments: LookupMap::new(StorageKey::Fulfillments),
        }
    }

    /// Owner only: rotate the signer key or change the payout account.
    pub fn set_signer(&mut self, seller: AccountId, signer_public_key: PublicKey) {
        require!(env::predecessor_account_id() == self.owner, "only owner");
        ed25519_bytes(&signer_public_key);
        self.seller = seller.clone();
        self.signer_public_key = signer_public_key.clone();
        emit_event(
            "signer_updated",
            json!({ "seller": seller, "signer_public_key": signer_public_key }),
        );
    }

    /// Buyer opens a request. The attached deposit is the budget held in escrow.
    #[payable]
    pub fn open_request(&mut self, min_quality: u8, ttl_seconds: u64, topic: String) -> U64 {
        let budget = env::attached_deposit();
        require!(budget > NearToken::from_yoctonear(0), "attach a deposit as the budget");
        require!(min_quality <= MAX_QUALITY, "min_quality must be 0 to 100");
        require!(ttl_seconds > 0 && ttl_seconds <= MAX_TTL_SECONDS, "ttl_seconds out of range");
        require!(topic.len() <= MAX_TOPIC_LEN, "topic too long");

        let id = self.next_request_id;
        self.next_request_id += 1;
        let now = env::block_timestamp();
        let request = SignalRequest {
            id: U64(id),
            buyer: env::predecessor_account_id(),
            budget: U128(budget.as_yoctonear()),
            min_quality,
            topic,
            created_at_ns: U64(now),
            deadline_ns: U64(now + ttl_seconds * NS_PER_SECOND),
            status: RequestStatus::Open,
        };
        emit_event("request_opened", &request);
        self.requests.insert(id, request);
        U64(id)
    }

    /// Anyone (usually the seller's oracle) submits a signed fulfillment.
    /// Panics, and so leaves the escrow untouched, if anything does not check out.
    pub fn fulfill(
        &mut self,
        request_id: U64,
        signal_id: String,
        keyed_hash: String,
        quality_score: u8,
        signature: String,
    ) -> Promise {
        let rid = request_id.0;
        let mut request = self.requests.get(&rid).cloned().unwrap_or_else(|| env::panic_str("unknown request"));
        require!(request.status == RequestStatus::Open, "request is not open");
        require!(env::block_timestamp() <= request.deadline_ns.0, "request deadline has passed");
        require!(valid_signal_id(&signal_id), "signal_id must be 1 to 64 chars of [A-Za-z0-9_-]");
        require!(keyed_hash.len() == 64 && is_lower_hex(&keyed_hash), "keyed_hash must be 64 lowercase hex chars");
        require!(quality_score <= MAX_QUALITY, "quality_score must be 0 to 100");

        let sig_bytes = hex::decode(&signature).unwrap_or_else(|_| env::panic_str("signature must be hex"));
        require!(sig_bytes.len() == 64, "signature must be 64 bytes");
        let mut sig = [0u8; 64];
        sig.copy_from_slice(&sig_bytes);
        let pk = ed25519_bytes(&self.signer_public_key);
        let msg = signing_message(
            env::current_account_id().as_str(),
            rid,
            &signal_id,
            &keyed_hash,
            quality_score,
        );
        require!(env::ed25519_verify(&sig, msg.as_bytes(), &pk), "invalid signature");
        require!(quality_score >= request.min_quality, "quality score below buyer minimum");

        request.status = RequestStatus::Fulfilled;
        let fulfillment = Fulfillment {
            request_id,
            signal_id,
            keyed_hash,
            quality_score,
            seller: self.seller.clone(),
            paid: request.budget,
            submitted_by: env::predecessor_account_id(),
            fulfilled_at_ns: U64(env::block_timestamp()),
        };
        emit_event("request_fulfilled", &fulfillment);
        self.requests.insert(rid, request.clone());
        self.fulfillments.insert(rid, fulfillment);
        Promise::new(self.seller.clone()).transfer(NearToken::from_yoctonear(request.budget.0))
    }

    /// After the deadline, anyone can return an unfulfilled budget to the buyer.
    pub fn refund(&mut self, request_id: U64) -> Promise {
        let rid = request_id.0;
        let mut request = self.requests.get(&rid).cloned().unwrap_or_else(|| env::panic_str("unknown request"));
        require!(request.status == RequestStatus::Open, "request is not open");
        require!(env::block_timestamp() > request.deadline_ns.0, "deadline has not passed yet");
        request.status = RequestStatus::Refunded;
        emit_event(
            "request_refunded",
            json!({ "request_id": request.id, "buyer": request.buyer, "amount": request.budget }),
        );
        self.requests.insert(rid, request.clone());
        Promise::new(request.buyer).transfer(NearToken::from_yoctonear(request.budget.0))
    }

    // ---------- views ----------

    pub fn get_config(&self) -> MarketConfig {
        MarketConfig {
            owner: self.owner.clone(),
            seller: self.seller.clone(),
            signer_public_key: self.signer_public_key.clone(),
            next_request_id: U64(self.next_request_id),
            signing_domain: SIGNING_DOMAIN.to_string(),
        }
    }

    pub fn get_request(&self, request_id: U64) -> Option<SignalRequest> {
        self.requests.get(&request_id.0).cloned()
    }

    pub fn get_requests(&self, from_index: Option<u64>, limit: Option<u64>) -> Vec<SignalRequest> {
        let from = from_index.unwrap_or(0) as usize;
        let limit = limit.unwrap_or(50).min(100) as usize;
        self.requests.values().skip(from).take(limit).cloned().collect()
    }

    pub fn get_fulfillment(&self, request_id: U64) -> Option<Fulfillment> {
        self.fulfillments.get(&request_id.0).cloned()
    }

    /// Helper so off chain signers can check they build the same bytes.
    pub fn get_signing_message(
        &self,
        request_id: U64,
        signal_id: String,
        keyed_hash: String,
        quality_score: u8,
    ) -> String {
        signing_message(env::current_account_id().as_str(), request_id.0, &signal_id, &keyed_hash, quality_score)
    }
}

#[cfg(test)]
mod tests;
