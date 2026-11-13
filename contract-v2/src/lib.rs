//! SAMPLE DATA keyword excerpt escrow on NEAR, Oralys's home chain.
//! Matching is attested by the oracle signature, not proved on chain.
use near_sdk::json_types::{U128, U64};
use near_sdk::serde::Serialize;
use near_sdk::serde_json::json;
use near_sdk::store::{IterableMap, LookupMap};
use near_sdk::{env, near, require, AccountId, BorshStorageKey, CurveType, NearToken, PanicOnDefault, Promise, PublicKey};

pub const EVENT_STANDARD: &str = "oralys_signal_market";
pub const EVENT_VERSION: &str = "2.0.0";
pub const SIGNING_DOMAIN: &str = "oralys-signal-v2";
pub const MAX_QUERY_LEN: usize = 256;
pub const MAX_EXCERPT_ID_LEN: usize = 64;
pub const MAX_TTL_SECONDS: u64 = 2_592_000;
pub const MAX_PAYOUTS_PER_REQUEST: u32 = 200;
pub const DEFAULT_WINDOW_SECONDS: u64 = 3600;
const NS_PER_SECOND: u64 = 1_000_000_000;
const MIN_PRICE: u128 = 1_000_000_000_000_000_000_000;

#[near(serializers = [borsh])]
#[derive(BorshStorageKey)]
enum StorageKey { Requests, Payouts, PayoutIds }

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub enum RequestStatus { Open, Exhausted, Refunded }

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug)]
pub struct KeywordRequest {
    pub id: U64,
    pub buyer: AccountId,
    pub query: String,
    pub window_seconds: u64,
    pub price_per_excerpt: U128,
    pub budget: U128,
    pub spent: U128,
    pub paid_count: u32,
    pub min_quality: u8,
    pub opened_at_ns: U64,
    pub deadline_ns: U64,
    pub status: RequestStatus,
}

#[near(serializers = [borsh, json])]
#[derive(Clone, Debug)]
pub struct ExcerptPayout {
    pub request_id: U64,
    pub excerpt_id: String,
    pub excerpt_hash: String,
    pub recorded_at: U64,
    pub quality_score: u8,
    pub seller: AccountId,
    pub paid: U128,
    pub submitted_by: AccountId,
    pub paid_at_ns: U64,
}

#[near(serializers = [json])]
pub struct MarketConfig {
    pub owner: AccountId,
    pub seller: AccountId,
    pub signer_public_key: PublicKey,
    pub next_request_id: U64,
    pub signing_domain: String,
    pub default_window_seconds: u64,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct KeywordMarket {
    owner: AccountId,
    seller: AccountId,
    signer_public_key: PublicKey,
    next_request_id: u64,
    requests: IterableMap<u64, KeywordRequest>,
    payouts: LookupMap<String, ExcerptPayout>,
    payout_ids: LookupMap<u64, Vec<String>>,
}

fn emit_event<T: Serialize>(event: &str, data: T) {
    env::log_str(&format!("EVENT_JSON:{}", json!({
        "standard": EVENT_STANDARD, "version": EVENT_VERSION,
        "event": event, "data": [data],
    })));
}

fn ed25519_bytes(pk: &PublicKey) -> [u8; 32] {
    require!(pk.curve_type() == CurveType::ED25519, "signer key must be ed25519");
    let raw = pk.as_bytes();
    require!(raw.len() == 33, "bad ed25519 key length");
    let mut out = [0u8; 32];
    out.copy_from_slice(&raw[1..]);
    out
}

fn is_lower_hex(s: &str) -> bool {
    s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn valid_excerpt_id(s: &str) -> bool {
    !s.is_empty() && s.len() <= MAX_EXCERPT_ID_LEN
        && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

pub fn signing_message(
    contract_id: &str, request_id: u64, excerpt_id: &str,
    excerpt_hash: &str, recorded_at: u64, quality_score: u8,
) -> String {
    format!("{}|{}|{}|{}|{}|{}|{}", SIGNING_DOMAIN, contract_id, request_id,
        excerpt_id, excerpt_hash, recorded_at, quality_score)
}

#[near]
impl KeywordMarket {
    #[init]
    pub fn new(owner: AccountId, seller: AccountId, signer_public_key: PublicKey) -> Self {
        ed25519_bytes(&signer_public_key);
        Self {
            owner, seller, signer_public_key, next_request_id: 0,
            requests: IterableMap::new(StorageKey::Requests),
            payouts: LookupMap::new(StorageKey::Payouts),
            payout_ids: LookupMap::new(StorageKey::PayoutIds),
        }
    }

    pub fn set_signer(&mut self, seller: AccountId, signer_public_key: PublicKey) {
        require!(env::predecessor_account_id() == self.owner, "only owner");
        ed25519_bytes(&signer_public_key);
        self.seller = seller.clone();
        self.signer_public_key = signer_public_key.clone();
        emit_event("signer_updated", json!({"seller": seller, "signer_public_key": signer_public_key}));
    }

    #[payable]
    pub fn open_request(&mut self, query: String, window_seconds: Option<u64>,
        price_per_excerpt: U128, min_quality: u8, ttl_seconds: u64) -> U64 {
        let budget = env::attached_deposit().as_yoctonear();
        require!(budget > 0, "attach a deposit as the budget");
        let query = query.trim().to_string();
        require!(!query.is_empty() && query.chars().count() <= MAX_QUERY_LEN, "query must be 1 to 256 chars");
        let window_seconds = window_seconds.unwrap_or(DEFAULT_WINDOW_SECONDS);
        require!((60..=604800).contains(&window_seconds), "window_seconds must be 60 to 604800");
        require!(price_per_excerpt.0 >= MIN_PRICE, "price_per_excerpt must be at least 0.001 NEAR");
        require!(budget >= price_per_excerpt.0, "deposit must cover at least one excerpt");
        require!(min_quality <= 100, "min_quality must be 0 to 100");
        require!(ttl_seconds > 0 && ttl_seconds <= MAX_TTL_SECONDS, "ttl_seconds out of range");
        let id = self.next_request_id;
        self.next_request_id += 1;
        let now = env::block_timestamp();
        let request = KeywordRequest {
            id: U64(id), buyer: env::predecessor_account_id(), query, window_seconds,
            price_per_excerpt, budget: U128(budget), spent: U128(0), paid_count: 0,
            min_quality, opened_at_ns: U64(now),
            deadline_ns: U64(now + ttl_seconds * NS_PER_SECOND), status: RequestStatus::Open,
        };
        emit_event("request_opened", &request);
        self.requests.insert(id, request);
        U64(id)
    }

    pub fn fulfill_excerpt(&mut self, request_id: U64, excerpt_id: String,
        excerpt_hash: String, recorded_at: U64, quality_score: u8, signature: String) -> Promise {
        let rid = request_id.0;
        let mut request = self.requests.get(&rid).cloned()
            .unwrap_or_else(|| env::panic_str("unknown request"));
        require!(request.status == RequestStatus::Open, "request is not open");
        let now = env::block_timestamp();
        require!(now <= request.deadline_ns.0, "request deadline has passed");
        require!(valid_excerpt_id(&excerpt_id), "excerpt_id must be 1 to 64 chars of [A-Za-z0-9_-]");
        require!(excerpt_hash.len() == 64 && is_lower_hex(&excerpt_hash), "excerpt_hash must be 64 lowercase hex chars");
        require!(quality_score <= 100, "quality_score must be 0 to 100");
        let sig_bytes = hex::decode(&signature).unwrap_or_else(|_| env::panic_str("signature must be hex"));
        require!(sig_bytes.len() == 64, "signature must be 64 bytes");
        let mut sig = [0u8; 64];
        sig.copy_from_slice(&sig_bytes);
        let pk = ed25519_bytes(&self.signer_public_key);
        let msg = signing_message(env::current_account_id().as_str(), rid, &excerpt_id,
            &excerpt_hash, recorded_at.0, quality_score);
        require!(env::ed25519_verify(&sig, msg.as_bytes(), &pk), "invalid signature");
        require!(recorded_at.0 <= now / NS_PER_SECOND, "recorded_at is in the future");
        let earliest = (request.opened_at_ns.0 / NS_PER_SECOND).saturating_sub(request.window_seconds);
        require!(recorded_at.0 >= earliest, "recorded_at is outside the request window");
        require!(quality_score >= request.min_quality, "quality score below buyer minimum");
        let key = format!("{}:{}", rid, excerpt_id);
        require!(!self.payouts.contains_key(&key), "excerpt already paid for this request");
        require!(request.budget.0 - request.spent.0 >= request.price_per_excerpt.0, "budget exhausted");

        request.spent.0 += request.price_per_excerpt.0;
        request.paid_count += 1;
        let exhausted = request.budget.0 - request.spent.0 < request.price_per_excerpt.0
            || request.paid_count >= MAX_PAYOUTS_PER_REQUEST;
        if exhausted { request.status = RequestStatus::Exhausted; }
        let payout = ExcerptPayout {
            request_id, excerpt_id: excerpt_id.clone(), excerpt_hash, recorded_at, quality_score,
            seller: self.seller.clone(), paid: request.price_per_excerpt,
            submitted_by: env::predecessor_account_id(), paid_at_ns: U64(now),
        };
        let mut ids = self.payout_ids.get(&rid).cloned().unwrap_or_default();
        ids.push(excerpt_id);
        self.payout_ids.insert(rid, ids);
        self.payouts.insert(key, payout.clone());
        self.requests.insert(rid, request.clone());
        emit_event("excerpt_paid", &payout);
        if exhausted { emit_event("request_exhausted", &request); }
        Promise::new(self.seller.clone()).transfer(NearToken::from_yoctonear(request.price_per_excerpt.0))
    }

    pub fn refund(&mut self, request_id: U64) -> Promise {
        let rid = request_id.0;
        let mut request = self.requests.get(&rid).cloned()
            .unwrap_or_else(|| env::panic_str("unknown request"));
        require!(request.status != RequestStatus::Refunded, "request already refunded");
        require!(env::block_timestamp() > request.deadline_ns.0, "deadline has not passed yet");
        let remaining = request.budget.0 - request.spent.0;
        require!(remaining > 0, "nothing to refund");
        request.status = RequestStatus::Refunded;
        self.requests.insert(rid, request.clone());
        emit_event("request_refunded", json!({"request_id": request.id, "buyer": request.buyer, "amount": U128(remaining)}));
        Promise::new(request.buyer).transfer(NearToken::from_yoctonear(remaining))
    }

    pub fn get_config(&self) -> MarketConfig {
        MarketConfig {
            owner: self.owner.clone(), seller: self.seller.clone(),
            signer_public_key: self.signer_public_key.clone(), next_request_id: U64(self.next_request_id),
            signing_domain: SIGNING_DOMAIN.into(), default_window_seconds: DEFAULT_WINDOW_SECONDS,
        }
    }
    pub fn get_request(&self, request_id: U64) -> Option<KeywordRequest> {
        self.requests.get(&request_id.0).cloned()
    }
    pub fn get_requests(&self, from_index: Option<u64>, limit: Option<u64>) -> Vec<KeywordRequest> {
        self.requests.values().skip(from_index.unwrap_or(0) as usize)
            .take(limit.unwrap_or(50).min(100) as usize).cloned().collect()
    }
    pub fn get_payouts(&self, request_id: U64) -> Vec<ExcerptPayout> {
        self.payout_ids.get(&request_id.0).into_iter().flatten()
            .filter_map(|id| self.payouts.get(&format!("{}:{}", request_id.0, id)).cloned()).collect()
    }
    pub fn is_paid(&self, request_id: U64, excerpt_id: String) -> bool {
        self.payouts.contains_key(&format!("{}:{}", request_id.0, excerpt_id))
    }
    pub fn get_signing_message(&self, request_id: U64, excerpt_id: String, excerpt_hash: String,
        recorded_at: U64, quality_score: u8) -> String {
        signing_message(env::current_account_id().as_str(), request_id.0, &excerpt_id,
            &excerpt_hash, recorded_at.0, quality_score)
    }
}

#[cfg(test)]
mod tests;
