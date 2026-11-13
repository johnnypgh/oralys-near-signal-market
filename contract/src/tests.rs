use super::*;
use ed25519_dalek::{Signer, SigningKey};
use near_sdk::test_utils::{get_logs, VMContextBuilder};
use near_sdk::testing_env;

const ONE_NEAR: u128 = 1_000_000_000_000_000_000_000_000;

fn contract_id() -> AccountId {
    "market.test.near".parse().unwrap()
}
fn owner() -> AccountId {
    "owner.test.near".parse().unwrap()
}
fn seller() -> AccountId {
    "seller.test.near".parse().unwrap()
}
fn buyer() -> AccountId {
    "buyer.test.near".parse().unwrap()
}

// Fixed test seed. Test key only, never used anywhere real.
fn test_signer() -> SigningKey {
    SigningKey::from_bytes(&[7u8; 32])
}

fn near_pk(key: &SigningKey) -> PublicKey {
    PublicKey::from_parts(CurveType::ED25519, key.verifying_key().to_bytes().to_vec()).unwrap()
}

fn ctx(predecessor: AccountId, deposit: u128, ts_ns: u64) {
    let mut b = VMContextBuilder::new();
    b.current_account_id(contract_id())
        .predecessor_account_id(predecessor.clone())
        .signer_account_id(predecessor)
        .attached_deposit(NearToken::from_yoctonear(deposit))
        .block_timestamp(ts_ns);
    testing_env!(b.build());
}

fn setup() -> SignalMarket {
    ctx(owner(), 0, 1_000);
    SignalMarket::new(owner(), seller(), near_pk(&test_signer()))
}

const HASH: &str = "3f1c2a9e8b7d6c5f4e3d2c1b0a99887766554433221100ffeeddccbbaa998877";

fn sign(key: &SigningKey, rid: u64, signal_id: &str, hash: &str, score: u8) -> String {
    let msg = signing_message(contract_id().as_str(), rid, signal_id, hash, score);
    hex::encode(key.sign(msg.as_bytes()).to_bytes())
}

fn open(c: &mut SignalMarket, min_q: u8, ttl: u64) -> u64 {
    ctx(buyer(), ONE_NEAR, 1_000);
    c.open_request(min_q, ttl, "sample-topic".into()).0
}

#[test]
fn open_request_escrows_budget_and_logs_event() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    let r = c.get_request(U64(id)).unwrap();
    assert_eq!(r.buyer, buyer());
    assert_eq!(r.budget.0, ONE_NEAR);
    assert_eq!(r.min_quality, 70);
    assert_eq!(r.deadline_ns.0, 1_000 + 60 * 1_000_000_000);
    assert_eq!(r.status, RequestStatus::Open);
    let logs = get_logs();
    assert!(logs[0].starts_with("EVENT_JSON:"));
    assert!(logs[0].contains("\"event\":\"request_opened\""));
    assert!(logs[0].contains("\"standard\":\"oralys_signal_market\""));
}

#[test]
fn valid_fulfillment_marks_paid() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    let sig = sign(&test_signer(), id, "sig-001", HASH, 82);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-001".into(), HASH.into(), 82, sig);
    let r = c.get_request(U64(id)).unwrap();
    assert_eq!(r.status, RequestStatus::Fulfilled);
    let f = c.get_fulfillment(U64(id)).unwrap();
    assert_eq!(f.quality_score, 82);
    assert_eq!(f.seller, seller());
    assert_eq!(f.paid.0, ONE_NEAR);
    assert!(get_logs().iter().any(|l| l.contains("\"event\":\"request_fulfilled\"")));
}

#[test]
fn score_exactly_at_minimum_is_accepted() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    let sig = sign(&test_signer(), id, "sig-edge", HASH, 70);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-edge".into(), HASH.into(), 70, sig);
    assert_eq!(c.get_request(U64(id)).unwrap().status, RequestStatus::Fulfilled);
}

#[test]
#[should_panic(expected = "invalid signature")]
fn signature_from_wrong_key_rejected() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    let imposter = SigningKey::from_bytes(&[9u8; 32]);
    let sig = sign(&imposter, id, "sig-001", HASH, 90);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-001".into(), HASH.into(), 90, sig);
}

#[test]
#[should_panic(expected = "invalid signature")]
fn tampered_score_rejected() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    // Signed for 55, submitted as 95.
    let sig = sign(&test_signer(), id, "sig-001", HASH, 55);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-001".into(), HASH.into(), 95, sig);
}

#[test]
#[should_panic(expected = "invalid signature")]
fn signature_for_other_request_rejected() {
    let mut c = setup();
    let id0 = open(&mut c, 10, 60);
    let id1 = open(&mut c, 10, 60);
    let sig_for_0 = sign(&test_signer(), id0, "sig-001", HASH, 90);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id1), "sig-001".into(), HASH.into(), 90, sig_for_0);
}

#[test]
#[should_panic(expected = "quality score below buyer minimum")]
fn score_below_minimum_rejected() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    let sig = sign(&test_signer(), id, "sig-low", HASH, 41);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-low".into(), HASH.into(), 41, sig);
}

#[test]
#[should_panic(expected = "request deadline has passed")]
fn fulfill_after_deadline_rejected() {
    let mut c = setup();
    let id = open(&mut c, 70, 1);
    let sig = sign(&test_signer(), id, "sig-late", HASH, 90);
    ctx(seller(), 0, 1_000 + 2_000_000_000);
    let _ = c.fulfill(U64(id), "sig-late".into(), HASH.into(), 90, sig);
}

#[test]
#[should_panic(expected = "request is not open")]
fn double_fulfill_rejected() {
    let mut c = setup();
    let id = open(&mut c, 10, 60);
    let sig = sign(&test_signer(), id, "sig-001", HASH, 90);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-001".into(), HASH.into(), 90, sig.clone());
    let _ = c.fulfill(U64(id), "sig-001".into(), HASH.into(), 90, sig);
}

#[test]
#[should_panic(expected = "keyed_hash must be 64 lowercase hex chars")]
fn bad_hash_rejected() {
    let mut c = setup();
    let id = open(&mut c, 10, 60);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-001".into(), "abc".into(), 90, "00".repeat(64));
}

#[test]
fn refund_after_deadline() {
    let mut c = setup();
    let id = open(&mut c, 70, 1);
    ctx(buyer(), 0, 1_000 + 2_000_000_000);
    let _ = c.refund(U64(id));
    assert_eq!(c.get_request(U64(id)).unwrap().status, RequestStatus::Refunded);
    assert!(get_logs().iter().any(|l| l.contains("\"event\":\"request_refunded\"")));
}

#[test]
#[should_panic(expected = "deadline has not passed yet")]
fn refund_before_deadline_rejected() {
    let mut c = setup();
    let id = open(&mut c, 70, 60);
    ctx(buyer(), 0, 2_000);
    let _ = c.refund(U64(id));
}

#[test]
#[should_panic(expected = "request is not open")]
fn refund_after_fulfill_rejected() {
    let mut c = setup();
    let id = open(&mut c, 10, 1);
    let sig = sign(&test_signer(), id, "sig-001", HASH, 90);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-001".into(), HASH.into(), 90, sig);
    ctx(buyer(), 0, 1_000 + 5_000_000_000);
    let _ = c.refund(U64(id));
}

#[test]
#[should_panic(expected = "attach a deposit as the budget")]
fn open_without_deposit_rejected() {
    let mut c = setup();
    ctx(buyer(), 0, 1_000);
    c.open_request(50, 60, "x".into());
}

#[test]
#[should_panic(expected = "min_quality must be 0 to 100")]
fn open_with_bad_min_quality_rejected() {
    let mut c = setup();
    ctx(buyer(), ONE_NEAR, 1_000);
    c.open_request(101, 60, "x".into());
}

#[test]
#[should_panic(expected = "only owner")]
fn set_signer_owner_only() {
    let mut c = setup();
    ctx(buyer(), 0, 1_000);
    c.set_signer(buyer(), near_pk(&test_signer()));
}

#[test]
fn rotated_signer_is_used() {
    let mut c = setup();
    let new_key = SigningKey::from_bytes(&[11u8; 32]);
    ctx(owner(), 0, 1_000);
    c.set_signer(seller(), near_pk(&new_key));
    let id = open(&mut c, 10, 60);
    let sig = sign(&new_key, id, "sig-002", HASH, 60);
    ctx(seller(), 0, 2_000);
    let _ = c.fulfill(U64(id), "sig-002".into(), HASH.into(), 60, sig);
    assert_eq!(c.get_request(U64(id)).unwrap().status, RequestStatus::Fulfilled);
}

#[test]
fn views_list_requests() {
    let mut c = setup();
    open(&mut c, 10, 60);
    open(&mut c, 20, 60);
    open(&mut c, 30, 60);
    let all = c.get_requests(None, None);
    assert_eq!(all.len(), 3);
    let page = c.get_requests(Some(1), Some(1));
    assert_eq!(page.len(), 1);
    assert_eq!(page[0].min_quality, 20);
    assert_eq!(c.get_config().next_request_id.0, 3);
}
