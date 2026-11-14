# SPEC: Oralys Signal Market

v1 technical specification for the pay-per-signal escrow contract and buyer agent.

## 1. Goal and track
NEAR hackathon (https://nearhackathon.com/), tracks Agent Economy (`agents`) plus Open Innovation (`open`). Deadline Sat Nov 14, 6:59 PM ET.
Build only the NEAR piece: a pay-per-signal escrow contract plus a buyer agent that pays for SAMPLE DATA transcript signals from Oralys,
a live-signal transcript data service whose home chain is NEAR. Project name: Oralys Signal Market. The Oralys app itself stays private and is not in this repo.

## 2. Hard rules
- Testnet or local sandbox only. No mainnet, no real money, no Intents execution (dry quotes only).
- Never print, log or commit keys. NEAR keys: `~/.near-credentials/testnet/`. Oracle keys: `.keys/` (gitignored). Model key: env `NEAR_AI_CLOUD_API_KEY`.
- All demo data is made up and labeled SAMPLE DATA. No private Oralys code or data.
- Present NEAR as Oralys's home chain. Do not mention Base anywhere in the README or docs, except as a cross-chain payment origin in the Intents quote example.
- No em dashes or en dashes anywhere. Plain wording, no invented figures.
- Do not commit secrets. `.keys/` and `~/.near-credentials` stay out of the tree.

## 3. Implemented state (Nov 12, 2026)
| Path | What | Status |
| --- | --- | --- |
| `contract/src/lib.rs` | Escrow contract, near-sdk 5.30, Rust stable 1.100, built with cargo-near 0.23 | builds; wasm sha256 bs58 `ACVxqCa67pvtCnBrvJzgFWndXbNQ8tF1zoVRgQSpKBFC` |
| `contract/src/tests.rs` | 18 unit tests | `cargo test`: 18 passed, 0 failed |
| `agent/src/near.ts` | near-api-js 7.5.3 helpers: `call` (never throws, returns hash/logs/events/error), `view`, balances, explorer links | used by all below |
| `agent/src/oracle.ts` | Seller oracle: ed25519 via node:crypto, HMAC-SHA256 keyed hash, signing message | covered by sandbox tests |
| `agent/src/buyer-agent.ts` | Budget, min quality, topic filter, `evaluate`, `openRequest`, `refund` | covered |
| `agent/src/seller.ts`, `feed.ts`, `env.ts` | Fulfill submitter, feed loader (rejects unlabeled data), sandbox/testnet setup + deploy/init | covered |
| `integration-tests/market.test.ts` | 9 sandbox tests (near-sandbox 0.3.5, node 2.14.0), incl. double fulfill | 9 passed, 0 failed |
| `scripts/demo.ts`, `scripts/demo.sh` | End to end readable demo, sandbox or testnet, writes each tx hash as it goes | sandbox run OK; testnet run completed Nov 12, 6:14 PM ET (`notes/testnet-run.md`) |
| `sample-data/signal-feed.json` | 6 made-up signals, scores 88/74/52/91/39/63, price 0.02 NEAR each | validated by intake check |
| `_tools/` and `stages/*/output/` | Pipeline scripts and recorded stage outputs | pipeline 01 to 04 passed all checks on sandbox |
| `_tools/test_tools.py` | 6 stdlib tests (rules, guard, dry quote) | 6 passed |
| `npx tsc --noEmit` | Typecheck | exit 0 |

Testnet state:
- `oralys-signal.testnet` (faucet funded), sub-accounts `market.`, `buyer.`, `seller.oralys-signal.testnet`, keys in `~/.near-credentials/testnet/`.
- Contract deployed on `market.oralys-signal.testnet`, code hash `ACVxqCa67pvtCnBrvJzgFWndXbNQ8tF1zoVRgQSpKBFC`, owner `oralys-signal.testnet`, seller `seller.oralys-signal.testnet`, signer `ed25519:6D2PVtfmgJybPk6PF8iKPHr33eQriJAHnR7YP7B6SSNr` (key in `.keys/oracle-testnet.json`).
- Request #0 (sample-001, 0.02 NEAR) is Fulfilled from an earlier interrupted run whose hashes were not captured.
- Final run, Nov 12, 6:14 PM ET: 10 txs, all hashes in `notes/testnet-run.json` and links in README: 4 opens (#1 to #4), 3 paid fulfills, 2 deliberate rejections (forged signature, score below minimum), 1 refund after deadline. The 3 low-score skips happen off chain in the buyer agent.
- Account creation tx: `8nVsDh5R6e1r6PkT5SYaBnLPoHfVKabhDxCjnQT5Cz7C`.

Attestation and model path:
- Added `_tools/attest.py`, the stage 02 attestation preflight and response signature check, fixtures and offline tests. Raw attestation reports get exact key redaction only (so they still verify), and `--require-attestation` refuses a base URL or model override.
- README.md, notes/intents-testnet.md and the sandbox double fulfill test are in the tree. A recorded run: 18 unit, 9 sandbox, 6 tools tests passed, tsc clean (`notes/test-run-2026-11-12.txt`).
- NEAR AI Cloud attestation for z-ai/glm-5.3-flash: preflight checks verified on the box without a key (Nov 12, 6:55 PM ET), gateway and model reports.
- Keyed completions, 3 runs. Run 1, Nov 12, 6:55 PM ET: HTTP 401, the tools read `NEAR_API_KEY`, which held a NEAR Builders key. Run 2, 7:08 PM ET: HTTP error, no reply, status not recorded (the tool now logs it). Run 3, 7:12 PM ET, `--require-attestation`: verified. provider_tee signature, ecdsa, signed text matches the exact request and response hashes, signer `0x3b753b4406613c5e70ae640508632b600424fa0c` matches exactly one verified model report, crypto check passed. Stage 02 output is `mode: model`, same buys as rules. Stage 04 report regenerated; settlement receipts are from the earlier sandbox run. The tools read `NEAR_AI_CLOUD_API_KEY` only and record HTTP status and error type of a failed completion. Record: `notes/near-ai-run.md`.

## 4. Known limits
- Buyers do not pay storage for their request records. The contract balance covers it.
- Payout transfers have no callback if the seller account vanished.
- One signer per contract.

## 5. Contract interface (`contract/src/lib.rs`)
Types: `U64`/`U128` are JSON strings. `PublicKey` is `"ed25519:<base58>"`. Status enum: `"Open" | "Fulfilled" | "Refunded"`.
Events: `EVENT_JSON:{"standard":"oralys_signal_market","version":"1.0.0","event":<name>,"data":[<obj>]}` (NEP-297 style).

| Method | Args | Deposit | Caller | State change | Event | Panics |
| --- | --- | --- | --- | --- | --- | --- |
| `new` (init) | `owner: AccountId, seller: AccountId, signer_public_key: PublicKey` | 0 | anyone, once | sets config, next id 0 | none | `signer key must be ed25519`, already initialized |
| `set_signer` | `seller: AccountId, signer_public_key: PublicKey` | 0 | owner | replaces seller and signer | `signer_updated` | `only owner`, `signer key must be ed25519` |
| `open_request` (payable) | `min_quality: u8, ttl_seconds: u64, topic: String` | budget > 0 yocto | anyone (buyer) | new request Open, deadline = now + ttl; returns `U64` id | `request_opened` (full request) | `attach a deposit as the budget`, `min_quality must be 0 to 100`, `ttl_seconds out of range` (1 to 2592000), `topic too long` (>128) |
| `fulfill` | `request_id: U64, signal_id: String, keyed_hash: String, quality_score: u8, signature: String` | 0 | anyone (oracle relayer) | request Fulfilled, stores Fulfillment, transfers full budget to `seller` | `request_fulfilled` (fulfillment) | `unknown request`, `request is not open`, `request deadline has passed`, `signal_id must be 1 to 64 chars of [A-Za-z0-9_-]`, `keyed_hash must be 64 lowercase hex chars`, `quality_score must be 0 to 100`, `signature must be hex`, `signature must be 64 bytes`, `invalid signature`, `quality score below buyer minimum` |
| `refund` | `request_id: U64` | 0 | anyone | request Refunded, budget back to buyer | `request_refunded` `{request_id, buyer, amount}` | `unknown request`, `request is not open`, `deadline has not passed yet` |
| `get_config` (view) | none | | | returns `{owner, seller, signer_public_key, next_request_id, signing_domain}` | | |
| `get_request` (view) | `request_id: U64` | | | `SignalRequest` or null | | |
| `get_requests` (view) | `from_index?: u64, limit?: u64` (default 50, max 100) | | | list | | |
| `get_fulfillment` (view) | `request_id: U64` | | | `{request_id, signal_id, keyed_hash, quality_score, seller, paid, submitted_by, fulfilled_at_ns}` or null | | |
| `get_signing_message` (view) | `request_id: U64, signal_id, keyed_hash, quality_score: u8` | | | the exact string to sign | | |

Order of checks in `fulfill`: open, deadline, field formats, signature, then score >= min. Signature is checked before the score, so a forged low score fails as `invalid signature`.

### Q&A: who enforces the minimum quality score?
The contract does, not just the agent. `open_request` stores `min_quality` (0 to 100, checked) on the request, and `fulfill` panics with "quality score below buyer minimum" when `quality_score < request.min_quality` (contract/src/lib.rs line 228), so no payment can be released below the buyer's bar. Because the score is inside the signed message, a seller cannot inflate it without breaking the signature check. The buyer agent also skips low-score signals before opening a request, which just saves gas. Covered by unit test `score_below_minimum_rejected` and the sandbox test for score below minimum.

## 6. Signature scheme
- Message (UTF-8 bytes, no hashing before signing):
  `oralys-signal-v1|<contract_account_id>|<request_id decimal>|<signal_id>|<keyed_hash lowercase hex>|<quality_score decimal>`
- Algorithm: ed25519 over those raw bytes; on chain `env::ed25519_verify(sig[64], msg, pk[32])`.
- `signature` arg: 128 lowercase hex chars (64 bytes). Public key registered as `ed25519:<base58 of 32 bytes>`.
- `keyed_hash` = HMAC-SHA256(oracle HMAC key, transcript UTF-8), lowercase hex. Transcript never goes on chain.
- Binding contract id and request id blocks replay across requests and deployments.

## 7. Test plan
Unit (`cd contract && cargo test`, all exist and pass): escrow and event on open; valid fulfill pays; score equal to min accepted; wrong key rejected; tampered score rejected; signature for another request rejected; score below min rejected; fulfill after deadline rejected; double fulfill rejected; bad hash rejected; refund after deadline; refund before deadline rejected; refund after fulfill rejected; open without deposit rejected; min_quality 101 rejected; set_signer owner only; rotated signer used; views paginate.
Sandbox (`npm run test:sandbox`, all exist and pass): config; signing message matches contract; success pays seller (balance delta = price minus gas); forged key rejected and escrow stays Open; tampered score rejected; score below min rejected and stays Open; refund after deadline (early refund rejected, late fulfill rejected, buyer balance up, status Refunded); agent skips low scores. Double fulfill is covered in the sandbox tests.
Tools (`python3 -I _tools/test_tools.py`): rules, budget cap, guard overrides a model buy the rules forbid, guard fills missing answers, model may skip, quote request always dry. The same command also runs `test_attest.py` and `test_evaluate_model.py` (attestation fixtures, signature binding, fallback labels, fake key leak test); 2 live network tests are skipped offline.

## 8. Pipeline
`policy.json` is the single home for numbers: budget 0.1 NEAR, min quality 70, price cap 0.05, ttl 600 s. `_tools/` holds the pipeline scripts. `_shared/buying-policy.md` explains how the policy is applied and is passed to the model in stage 02.

| Stage | Inputs | Process | Output | Check | Model |
| --- | --- | --- | --- | --- | --- |
| 01_intake | `sample-data/signal-feed.json` | `python3 -I _tools/intake.py` | `stages/01_intake/output/feed.json` | `intake.py --check` | none (script) |
| 02_evaluate | feed, `_shared/policy.json`, `_shared/buying-policy.md` | `python3 -I _tools/evaluate.py` (auto) | `stages/02_evaluate/output/decisions.json` | `evaluate.py --check` | z-ai/glm-5.3-flash at https://cloud-api.near.ai/v1 with `NEAR_AI_CLOUD_API_KEY`; unset key: none (script) rules engine. Model sees metadata only; guard re-applies hard rules. Preflight: `GET /v1/attestation/report?provider=near` with a fresh nonce and `x-no-aliasing: true`, checked by `_tools/attest.py` (DCAP, nonce and signer binding, MRCONFIGID, RTMR3, NVIDIA NRAS). After the completion: `GET /v1/signature/<id>` with the same `signing_algo`; a `provider_tee` signer must match exactly one verified model report. `--require-attestation` falls back to rules on any attestation failure |
| 03_settle | decisions, feed, policy, wasm | `npx tsx _tools/settle.ts --network sandbox|testnet` | `stages/03_settle/output/receipts.json` | `python3 -I _tools/check_receipts.py` | none (script) |
| 04_report | decisions, receipts | `python3 -I _tools/report.py` | `stages/04_report/output/report.md` | `report.py --check` (no dashes, SAMPLE DATA, matches files) | none (script) |
| 05_intents_quote | `_tools/intents_quote.py` | `python3 -I _tools/intents_quote.py --amount-usdc 1` | `stages/05_intents_quote/output/quote.json` | `intents_quote.py --check` (dry, no deposit address) | none (script) |
All at once: `_tools/run_pipeline.sh [sandbox|testnet]` (set `SKIP_INTENTS_QUOTE=1` to skip 05). The model path of 02 has one verified run (Nov 12, 7:12 PM ET, provider_tee signature verified), see `notes/near-ai-run.md`.

## 9. Intents stretch: dry quote only
- NEAR Intents has no testnet and no plans for one: https://docs.near-intents.org/resources/faqs and the warning at https://docs.near-intents.org/integration/distribution-channels/1click-api/quickstart/introduction
- Quote endpoint `POST https://1click.chaindefuser.com/v0/quote`; `"dry": true` returns pricing with no deposit address: https://docs.near-intents.org/api-reference/oneclick/request-a-swap-quote (OpenAPI https://1click.chaindefuser.com/docs/v0/openapi.yaml). Token ids from `GET https://1click.chaindefuser.com/v0/tokens`.
- Without a JWT an extra 0.25% fee applies (quickstart page). Requests need a User-Agent header (Cloudflare returned 1010 without one).
- `_tools/intents_quote.py`: example origin USDC on Base `nep141:base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near`, destination NEAR USDC `nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1`, placeholder recipient and refund address. Ran once on Nov 12 about 5:57 PM ET: HTTP 201, amountIn 1000000, amountOut 995521, no deposit address. Nothing signed, deposited or spent.

## 10. Expected outputs
- 01: `CHECK OK: ... has 6 SAMPLE DATA signals`
- 02 (rules): buys sample-001, 002, 004; `planned spend=0.06 NEAR (budget 0.1)`
- 03: three receipts, status Fulfilled, `CHECK OK: ... 3 fulfilled on market.<root>`
- 04: report table of 6 rows; `CHECK OK`
- 05: `CHECK OK: ... dry quote ... no deposit address`
- `scripts/demo.sh`: setup txs; agent BUY 001, 002, 004 and SKIP 003, 005, 006 with reasons; seller balance up about 0.059 NEAR; guardrails: forged signature REJECTED `invalid signature`, score 74 vs min 80 REJECTED `quality score below buyer minimum`, refund after ~25 s REFUNDED; summary 15 txs, 2 rejected on purpose. Writes `demo-output/demo-<network>.log` and `-txs.json` (testnet adds nearblocks links).

## 11. Testnet deploy steps (placeholders)
```
cd contract && cargo near build non-reproducible-wasm && cd ..
# account already exists: oralys-signal.testnet. For a new one:
# near account create-account sponsor-by-faucet-service <ACCOUNT>.testnet autogenerate-new-keypair save-to-legacy-keychain network-config testnet create
NEAR_ACCOUNT_ID=<ACCOUNT>.testnet scripts/demo.sh testnet          # creates/reuses market., buyer., seller. sub-accounts, deploys, runs
NEAR_ACCOUNT_ID=<ACCOUNT>.testnet _tools/run_pipeline.sh testnet  # pipeline run against the deployed contract
```
Optional env: `NEAR_RPC_URL` (default https://test.rpc.fastnear.com), `MARKET_FUNDING_NEAR` 3, `BUYER_FUNDING_NEAR` 1, `SELLER_FUNDING_NEAR` 0.2.
Explorer: `https://testnet.nearblocks.io/address/market.<ACCOUNT>.testnet`.

## 12. Toolchain (checked on the box Nov 12, 2026, about 6:20 PM ET)
- The contract pins `channel = "stable"` in `contract/rust-toolchain.toml`, so rustup builds it with stable, currently `rustc 1.100.0` / `cargo 1.100.0`. Run `rustup show active-toolchain` inside `contract/` to confirm.
- Dependency MSRV: near-sdk 5.30.1 and its near-sdk-* crates declare `rust-version = 1.95`. Any toolchain older than 1.95 fails. (Earlier reports of "1.88" and "1.85.1" were wrong or came from the wrong binary.)
- The box also has a distro Rust at `/usr/bin/rustc` and `/usr/bin/cargo` (1.85.1). It cannot build this project. Put `~/.cargo/bin` first on PATH so rustup's `cargo` is used. The rustup default was 1.81.0 by mistake and is now `stable`; the pin above makes the default irrelevant inside `contract/`.
- Build tools: cargo-near 0.23.0 (`cargo near build non-reproducible-wasm`, which runs wasm-opt and embeds the ABI), near-cli-rs 0.31.1, Node v24.22.1, Python 3.13.5. Wasm target: `wasm32-unknown-unknown` on the stable toolchain.
- Wasm built with Rust 1.87 or newer uses bulk-memory opcodes. That needs NEAR protocol 84 or later. near-sdk 5.30 declares this, and testnet and near-sandbox 2.14.0 accept it (the contract is deployed on testnet).
