use super::*;
use ed25519_dalek::{Signer, SigningKey};
use near_sdk::test_utils::{get_created_receipts, get_logs, VMContextBuilder};
use near_sdk::testing_env;

const PRICE: u128 = 10 * MIN_PRICE;
const NOW: u64 = 10_000;
const HASH: &str = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
fn account(name: &str) -> AccountId { format!("{}.test.near", name).parse().unwrap() }
// Throwaway test key constructed only in memory. Never used on a live chain.
fn signer() -> SigningKey { SigningKey::from_bytes(&[7u8; 32]) }
fn pk(key: &SigningKey) -> PublicKey {
    PublicKey::from_parts(CurveType::ED25519, key.verifying_key().to_bytes().to_vec()).unwrap()
}
fn ctx(who: &str, deposit: u128, seconds: u64) {
    let mut b = VMContextBuilder::new();
    b.current_account_id(account("market")).predecessor_account_id(account(who))
        .signer_account_id(account(who)).attached_deposit(NearToken::from_yoctonear(deposit))
        .block_timestamp(seconds * NS_PER_SECOND);
    testing_env!(b.build());
}
fn setup() -> KeywordMarket {
    ctx("owner", 0, NOW);
    KeywordMarket::new(account("owner"), account("seller"), pk(&signer()))
}
fn open(c: &mut KeywordMarket, budget: u128) -> U64 {
    ctx("buyer", budget, NOW);
    let id = c.open_request("SAMPLE DATA NVIDIA".into(), None, U128(PRICE), 70, 60);
    ctx("relayer", 0, NOW);
    id
}
fn signature(rid: U64, id: &str, hash: &str, recorded: u64, score: u8) -> String {
    let msg = signing_message(account("market").as_str(), rid.0, id, hash, recorded, score);
    hex::encode(signer().sign(msg.as_bytes()).to_bytes())
}
fn pay(c: &mut KeywordMarket, rid: U64, id: &str, recorded: u64, score: u8) {
    let sig = signature(rid, id, HASH, recorded, score);
    drop(c.fulfill_excerpt(rid, id.into(), HASH.into(), U64(recorded), score, sig));
}
fn request(c: &KeywordMarket, rid: U64) -> KeywordRequest { c.get_request(rid).unwrap() }
fn event(name: &str) -> near_sdk::serde_json::Value {
    get_logs().iter().filter_map(|l| l.strip_prefix("EVENT_JSON:"))
        .map(|l| near_sdk::serde_json::from_str::<near_sdk::serde_json::Value>(l).unwrap())
        .find(|v| v["event"] == name).unwrap()
}

macro_rules! bad_open {
    ($name:ident, $message:literal, $budget:expr, $query:expr, $window:expr, $price:expr, $quality:expr, $ttl:expr) => {
        #[test]
        #[should_panic(expected = $message)]
        fn $name() {
            let mut c = setup();
            ctx("buyer", $budget, NOW);
            c.open_request($query.into(), $window, U128($price), $quality, $ttl);
        }
    };
}
bad_open!(zero_deposit, "attach a deposit as the budget", 0, "", Some(0), 0, 101, 0);
bad_open!(empty_query, "query must be 1 to 256 chars", PRICE, "", None, PRICE, 70, 60);
bad_open!(blank_query, "query must be 1 to 256 chars", PRICE, " \n\t ", None, PRICE, 70, 60);
bad_open!(long_query, "query must be 1 to 256 chars", PRICE, "a".repeat(257), None, PRICE, 70, 60);
bad_open!(short_window, "window_seconds must be 60 to 604800", PRICE, "a", Some(59), PRICE, 70, 60);
bad_open!(long_window, "window_seconds must be 60 to 604800", PRICE, "a", Some(604801), PRICE, 70, 60);
bad_open!(low_price, "price_per_excerpt must be at least 0.001 NEAR", PRICE, "a", None, MIN_PRICE-1, 70, 60);
bad_open!(small_budget, "deposit must cover at least one excerpt", PRICE-1, "a", None, PRICE, 70, 60);
bad_open!(bad_min_quality, "min_quality must be 0 to 100", PRICE, "a", None, PRICE, 101, 60);
bad_open!(zero_ttl, "ttl_seconds out of range", PRICE, "a", None, PRICE, 70, 0);
bad_open!(long_ttl, "ttl_seconds out of range", PRICE, "a", None, PRICE, 70, MAX_TTL_SECONDS+1);

macro_rules! bad_fulfill {
    ($name:ident, $message:literal, $id:expr, $hash:expr, $recorded:expr, $score:expr, $sig:expr) => {
        #[test]
        #[should_panic(expected = $message)]
        fn $name() {
            let mut c = setup(); let rid = open(&mut c, 3*PRICE);
            drop(c.fulfill_excerpt(rid, $id.into(), $hash.into(), U64($recorded), $score, $sig.into()));
        }
    };
}
bad_fulfill!(empty_id, "excerpt_id must be 1 to 64 chars of [A-Za-z0-9_-]", "", HASH, NOW, 80, "");
bad_fulfill!(long_id, "excerpt_id must be 1 to 64 chars of [A-Za-z0-9_-]", "a".repeat(65), HASH, NOW, 80, "");
bad_fulfill!(punctuation_id, "excerpt_id must be 1 to 64 chars of [A-Za-z0-9_-]", "a:b", HASH, NOW, 80, "");
bad_fulfill!(unicode_id, "excerpt_id must be 1 to 64 chars of [A-Za-z0-9_-]", "é", HASH, NOW, 80, "");
bad_fulfill!(short_hash, "excerpt_hash must be 64 lowercase hex chars", "a", "a", NOW, 80, "");
bad_fulfill!(uppercase_hash, "excerpt_hash must be 64 lowercase hex chars", "a", HASH.to_uppercase(), NOW, 80, "");
bad_fulfill!(nonhex_hash, "excerpt_hash must be 64 lowercase hex chars", "a", "g".repeat(64), NOW, 80, "");
bad_fulfill!(bad_score, "quality_score must be 0 to 100", "a", HASH, NOW, 101, "");
bad_fulfill!(nonhex_signature, "signature must be hex", "a", HASH, NOW, 80, "zz");
bad_fulfill!(odd_signature, "signature must be hex", "a", HASH, NOW, 80, "a");
bad_fulfill!(short_signature, "signature must be 64 bytes", "a", HASH, NOW, 80, "00".repeat(63));
bad_fulfill!(long_signature, "signature must be 64 bytes", "a", HASH, NOW, 80, "00".repeat(65));
bad_fulfill!(invalid_signature, "invalid signature", "a", HASH, NOW, 80, "00".repeat(64));

macro_rules! bad_pay {
    ($name:ident, $message:literal, $recorded:expr, $score:expr) => {
        #[test]
        #[should_panic(expected = $message)]
        fn $name() { let mut c = setup(); let rid = open(&mut c, 3*PRICE); pay(&mut c, rid, "a", $recorded, $score); }
    };
}
bad_pay!(future_recording, "recorded_at is in the future", NOW+1, 80);
bad_pay!(old_recording, "recorded_at is outside the request window", NOW-3601, 80);
bad_pay!(low_quality, "quality score below buyer minimum", NOW, 69);

#[test]
#[should_panic(expected = "unknown request")]
fn unknown_fulfill() { let mut c = setup(); pay(&mut c, U64(99), "a", NOW, 80); }
#[test]
#[should_panic(expected = "request is not open")]
fn exhausted_fulfill() { let mut c = setup(); let id = open(&mut c, PRICE); pay(&mut c,id,"a",NOW,80); pay(&mut c,id,"b",NOW,80); }
#[test]
#[should_panic(expected = "request is not open")]
fn refunded_fulfill() {
    let mut c=setup(); let id=open(&mut c,PRICE); ctx("relayer",0,NOW+61);
    drop(c.refund(id)); pay(&mut c,id,"a",NOW,80);
}
#[test]
#[should_panic(expected = "request deadline has passed")]
fn late_fulfill() { let mut c=setup(); let id=open(&mut c,PRICE); ctx("relayer",0,NOW+61); pay(&mut c,id,"a",NOW,80); }
#[test]
#[should_panic(expected = "excerpt already paid for this request")]
fn duplicate() { let mut c=setup(); let id=open(&mut c,3*PRICE); pay(&mut c,id,"a",NOW,80); pay(&mut c,id,"a",NOW,80); }
#[test]
#[should_panic(expected = "budget exhausted")]
fn defensive_budget_check() {
    let mut c=setup(); let id=open(&mut c,PRICE);
    // Unreachable via public methods: exercise the specified defensive guard.
    c.requests.get_mut(&id.0).unwrap().spent=U128(PRICE);
    pay(&mut c,id,"a",NOW,80);
}
#[test]
#[should_panic(expected = "unknown request")]
fn unknown_refund() { let mut c=setup(); drop(c.refund(U64(99))); }
#[test]
#[should_panic(expected = "request already refunded")]
fn double_refund() { let mut c=setup(); let id=open(&mut c,PRICE); ctx("relayer",0,NOW+61); drop(c.refund(id)); drop(c.refund(id)); }
#[test]
#[should_panic(expected = "deadline has not passed yet")]
fn early_refund() { let mut c=setup(); let id=open(&mut c,PRICE); drop(c.refund(id)); }
#[test]
#[should_panic(expected = "deadline has not passed yet")]
fn refund_at_deadline() { let mut c=setup(); let id=open(&mut c,PRICE); ctx("relayer",0,NOW+60); drop(c.refund(id)); }
#[test]
#[should_panic(expected = "nothing to refund")]
fn empty_refund() { let mut c=setup(); let id=open(&mut c,PRICE); pay(&mut c,id,"a",NOW,80); ctx("relayer",0,NOW+61); drop(c.refund(id)); }

macro_rules! tampered {
    ($name:ident, $message:expr) => {
        #[test]
        #[should_panic(expected = "invalid signature")]
        fn $name() {
            let mut c=setup(); let id=open(&mut c,PRICE);
            let msg: String=$message;
            let sig=hex::encode(signer().sign(msg.as_bytes()).to_bytes());
            drop(c.fulfill_excerpt(id,"a".into(),HASH.into(),U64(NOW),80,sig));
        }
    };
}
tampered!(tampered_recorded_at, signing_message(account("market").as_str(),0,"a",HASH,NOW-1,80));
tampered!(tampered_score, signing_message(account("market").as_str(),0,"a",HASH,NOW,81));
tampered!(wrong_contract, signing_message("other.test.near",0,"a",HASH,NOW,80));
tampered!(wrong_request, signing_message(account("market").as_str(),1,"a",HASH,NOW,80));
tampered!(wrong_excerpt, signing_message(account("market").as_str(),0,"b",HASH,NOW,80));
tampered!(wrong_hash, signing_message(account("market").as_str(),0,"a",&"0".repeat(64),NOW,80));
tampered!(v1_domain, format!("oralys-signal-v1|market.test.near|0|a|{}|{}|80",HASH,NOW));
tampered!(v1_format, format!("oralys-signal-v1|market.test.near|0|a|{}|80",HASH));

#[test]
fn config_and_default_window() {
    let mut c=setup(); let id=open(&mut c,4*PRICE); let cfg=c.get_config();
    assert_eq!(cfg.signing_domain,"oralys-signal-v2"); assert_eq!(cfg.default_window_seconds,3600);
    assert_eq!(cfg.owner,account("owner")); assert_eq!(cfg.seller,account("seller"));
    assert_eq!(cfg.signer_public_key,pk(&signer())); assert_eq!(cfg.next_request_id.0,1);
    let r=request(&c,id); assert_eq!(r.window_seconds,3600); assert_eq!(r.spent.0,0);
    assert_eq!(r.opened_at_ns.0,NOW*NS_PER_SECOND); assert_eq!(r.deadline_ns.0,(NOW+60)*NS_PER_SECOND);
}
#[test]
fn custom_window_and_trimmed_query() {
    let mut c=setup(); ctx("buyer",PRICE,NOW);
    let id=c.open_request("  SAMPLE DATA NVIDIA  ".into(),Some(7200),U128(PRICE),70,60);
    assert_eq!(request(&c,id).query,"SAMPLE DATA NVIDIA"); assert_eq!(request(&c,id).window_seconds,7200);
    ctx("relayer",0,NOW); pay(&mut c,id,"a",NOW-7200,80);
}
#[test]
fn inclusive_open_limits() {
    let mut c=setup(); ctx("buyer",MIN_PRICE,NOW);
    let a=c.open_request("a".repeat(256),Some(60),U128(MIN_PRICE),0,1);
    ctx("buyer",MIN_PRICE,NOW);
    let b=c.open_request("é".repeat(256),Some(604800),U128(MIN_PRICE),100,MAX_TTL_SECONDS);
    assert_eq!(request(&c,a).min_quality,0); assert_eq!(request(&c,b).min_quality,100);
}
#[test]
fn signing_message_exact() {
    let c=setup(); let expected=format!("oralys-signal-v2|market.test.near|42|sd-r1-s1|{}|10000|80",HASH);
    assert_eq!(signing_message("market.test.near",42,"sd-r1-s1",HASH,NOW,80),expected);
    assert_eq!(c.get_signing_message(U64(42),"sd-r1-s1".into(),HASH.into(),U64(NOW),80),expected);
}
#[test]
fn happy_path_payout_and_transfer() {
    let mut c=setup(); let id=open(&mut c,4*PRICE); pay(&mut c,id,"sd-A_1",NOW-5,80);
    let r=request(&c,id); assert_eq!(r.spent.0,PRICE); assert_eq!(r.paid_count,1); assert_eq!(r.status,RequestStatus::Open);
    let payouts=c.get_payouts(id); assert_eq!(payouts.len(),1); let p=&payouts[0];
    assert_eq!(p.request_id,id); assert_eq!(p.excerpt_id,"sd-A_1"); assert_eq!(p.excerpt_hash,HASH);
    assert_eq!(p.recorded_at.0,NOW-5); assert_eq!(p.quality_score,80); assert_eq!(p.paid.0,PRICE);
    assert_eq!(p.seller,account("seller")); assert_eq!(p.submitted_by,account("relayer"));
    assert_eq!(p.paid_at_ns.0,NOW*NS_PER_SECOND); assert!(c.is_paid(id,"sd-A_1".into()));
    assert_eq!(get_created_receipts()[0].receiver_id,account("seller"));
    let e=event("excerpt_paid"); assert_eq!(e["standard"],EVENT_STANDARD); assert_eq!(e["version"],EVENT_VERSION);
    assert_eq!(e["data"][0]["paid"],PRICE.to_string());
}
#[test]
fn four_payouts_in_pay_order() {
    let mut c=setup(); let id=open(&mut c,4*PRICE);
    for name in ["z","a","c","b"] { ctx("relayer",0,NOW); pay(&mut c,id,name,NOW,80); }
    let r=request(&c,id); assert_eq!(r.paid_count,4); assert_eq!(r.spent.0,4*PRICE); assert_eq!(r.status,RequestStatus::Exhausted);
    assert_eq!(c.get_payouts(id).iter().map(|p|p.excerpt_id.as_str()).collect::<Vec<_>>(),vec!["z","a","c","b"]);
    assert_eq!(event("request_exhausted")["data"][0]["paid_count"],4);
}
#[test]
fn window_lower_edge() { let mut c=setup(); let id=open(&mut c,PRICE); pay(&mut c,id,"a",NOW-3600,70); assert_eq!(request(&c,id).paid_count,1); }
#[test]
fn current_time_and_quality_upper_edge() { let mut c=setup(); let id=open(&mut c,PRICE); pay(&mut c,id,"a",NOW,100); assert!(c.is_paid(id,"a".into())); }
#[test]
fn exact_deadline_payment() { let mut c=setup(); let id=open(&mut c,PRICE); ctx("relayer",0,NOW+60); pay(&mut c,id,"a",NOW+60,80); assert_eq!(request(&c,id).paid_count,1); }
#[test]
fn lower_window_saturates_at_zero() {
    let mut c=setup(); ctx("buyer",PRICE,10);
    let id=c.open_request("SAMPLE DATA".into(),None,U128(PRICE),70,60);
    ctx("relayer",0,10); pay(&mut c,id,"a",0,80); assert_eq!(request(&c,id).paid_count,1);
}
#[test]
fn max_length_id() { let mut c=setup(); let id=open(&mut c,PRICE); pay(&mut c,id,&"a".repeat(64),NOW,80); assert_eq!(request(&c,id).paid_count,1); }
#[test]
fn same_excerpt_two_requests() {
    let mut c=setup(); let a=open(&mut c,2*PRICE); let b=open(&mut c,2*PRICE);
    pay(&mut c,a,"a",NOW,80); pay(&mut c,b,"a",NOW,80);
    assert!(c.is_paid(a,"a".into())); assert!(c.is_paid(b,"a".into()));
    assert_eq!(c.get_payouts(a)[0].request_id,a); assert_eq!(c.get_payouts(b)[0].request_id,b);
}
#[test]
fn full_refund() {
    let mut c=setup(); let id=open(&mut c,3*PRICE); ctx("relayer",0,NOW+61); drop(c.refund(id));
    assert_eq!(request(&c,id).status,RequestStatus::Refunded); assert_eq!(request(&c,id).spent.0,0);
    assert_eq!(event("request_refunded")["data"][0]["amount"],(3*PRICE).to_string());
    assert_eq!(get_created_receipts()[0].receiver_id,account("buyer"));
}
#[test]
fn open_remainder_refund() {
    let mut c=setup(); let id=open(&mut c,3*PRICE); pay(&mut c,id,"a",NOW,80);
    ctx("relayer",0,NOW+61); drop(c.refund(id));
    assert_eq!(request(&c,id).status,RequestStatus::Refunded); assert_eq!(request(&c,id).spent.0,PRICE);
    assert_eq!(event("request_refunded")["data"][0]["amount"],(2*PRICE).to_string());
    assert!(c.is_paid(id,"a".into()));
}
#[test]
fn exhausted_remainder_refund() {
    let mut c=setup(); let id=open(&mut c,PRICE+MIN_PRICE); pay(&mut c,id,"a",NOW,80);
    assert_eq!(request(&c,id).status,RequestStatus::Exhausted);
    ctx("relayer",0,NOW+61); drop(c.refund(id));
    assert_eq!(request(&c,id).status,RequestStatus::Refunded);
    assert_eq!(event("request_refunded")["data"][0]["amount"],MIN_PRICE.to_string());
}
#[test]
fn payout_cap_and_refund() {
    let mut c=setup(); let id=open(&mut c,201*PRICE);
    for i in 0..200 { ctx("relayer",0,NOW); pay(&mut c,id,&format!("a{}",i),NOW,80); }
    let r=request(&c,id); assert_eq!(r.paid_count,200); assert_eq!(r.spent.0,200*PRICE);
    assert_eq!(r.status,RequestStatus::Exhausted); assert_eq!(c.get_payouts(id).len(),200);
    ctx("relayer",0,NOW+61); drop(c.refund(id));
    assert_eq!(event("request_refunded")["data"][0]["amount"],PRICE.to_string());
}
#[test]
fn empty_views_and_pagination() {
    let mut c=setup(); assert!(c.get_request(U64(99)).is_none()); assert!(c.get_payouts(U64(99)).is_empty());
    assert!(!c.is_paid(U64(99),"a".into())); assert!(c.get_requests(None,None).is_empty());
    for _ in 0..3 { open(&mut c,PRICE); }
    assert_eq!(c.get_requests(Some(1),Some(1))[0].id.0,1);
    assert!(c.get_requests(Some(3),None).is_empty()); assert!(c.get_requests(None,Some(0)).is_empty());
}
#[test]
fn owner_rotation() {
    let mut c=setup(); let key=SigningKey::from_bytes(&[8u8;32]);
    c.set_signer(account("new-seller"),pk(&key)); let id=open(&mut c,PRICE);
    let msg=signing_message(account("market").as_str(),id.0,"a",HASH,NOW,80);
    drop(c.fulfill_excerpt(id,"a".into(),HASH.into(),U64(NOW),80,hex::encode(key.sign(msg.as_bytes()).to_bytes())));
    assert_eq!(c.get_payouts(id)[0].seller,account("new-seller"));
}
#[test]
#[should_panic(expected="only owner")]
fn nonowner_rotation() { let mut c=setup(); ctx("buyer",0,NOW); c.set_signer(account("seller"),pk(&signer())); }
#[test]
#[should_panic(expected="signer key must be ed25519")]
fn wrong_curve() {
    ctx("owner",0,NOW);
    KeywordMarket::new(account("owner"),account("seller"),PublicKey::from_parts(CurveType::SECP256K1,vec![0;64]).unwrap());
}
