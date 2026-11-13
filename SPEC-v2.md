# SPEC v2: keyword requests, pay per excerpt

Status: approved by John Nov 12, 2026, 11:40 PM ET ("Go on the keyword version with the Fri 6 PM ET cutoff and today's version as backup"). Branch `v2-keyword`. v1 (`SPEC.md`, `contract/`, branch `publish` at c466a59) stays as is and is the fallback. No push.

## 1. What changes
A buyer agent asks for keywords, for example `NVIDIA OR (Clarity AND Act)`, and pays for a portion of the transcript each time those keywords are hit in recordings on the platform within the last `window_seconds` (set by the buyer, default 3600). The deposit is the budget cap. Each paid excerpt pays a fixed price to the platform (seller) account. The money moves only when the excerpt meets the buyer's quality bar.

Recorders are compensated afterward by the platform in tokens. They can swap the tokens to USDC or give them to agents, their own or others, who spend them in the marketplace. This happens off contract and is not part of the demo.

The keyword matching is done by the Oralys oracle off chain and attested by its ed25519 signature. It is not proved on chain. The chain checks the signature, the window, the quality score, double pay and the budget.

## 2. DEFAULTS (John has not answered these; change them if he does)
- Query syntax: terms joined by AND / OR, parentheses, and quoted phrases. Nothing else: no NOT, no wildcards, no commas. Operators are case insensitive. Two terms with no operator between them are an error.
- Price: a fixed `price_per_excerpt` set by the buyer per request, demo value 0.01 NEAR, minimum 0.001 NEAR. The deposit caps total spend.
- Excerpt: the matching sentence plus one sentence of context on each side, capped at 400 characters (drop the context first, then cut the sentence at a word boundary).
- An AND group must be satisfied inside one excerpt.
- Pay once per excerpt per request. Excerpts in one segment do not overlap.
- Window: buyer sets it, default 3600 s, allowed 60 s to 604800 s (7 days).

## 3. Contract (`contract-v2/`, new crate, v1 `contract/` untouched)
Deploy target: `market2.oralys-signal.testnet` (new sub-account, Bob creates it and deploys, not OpenClaw). Same init and owner model as v1: `new(owner, seller, signer_public_key)`, `set_signer(seller, signer_public_key)` owner only.

Constants: `SIGNING_DOMAIN = "oralys-signal-v2"`, `EVENT_VERSION = "2.0.0"`, standard `oralys_signal_market`, `MAX_QUERY_LEN = 256`, `MAX_EXCERPT_ID_LEN = 64`, `MAX_TTL_SECONDS = 2592000`, `MAX_PAYOUTS_PER_REQUEST = 200`.

Signed message (UTF-8, exact): `oralys-signal-v2|<contract id>|<request id>|<excerpt id>|<excerpt hash>|<recorded_at unix seconds>|<quality score>`

| Method | Args | Checks, in order, with exact panic text |
| --- | --- | --- |
| `open_request` (payable) | `query: String, window_seconds: Option<u64>, price_per_excerpt: U128, min_quality: u8, ttl_seconds: u64` -> `U64` | deposit > 0 `attach a deposit as the budget`; trimmed query non-empty and len <= 256 `query must be 1 to 256 chars`; window in range `window_seconds must be 60 to 604800`; price >= 0.001 NEAR `price_per_excerpt must be at least 0.001 NEAR`; deposit >= price `deposit must cover at least one excerpt`; `min_quality must be 0 to 100`; `ttl_seconds out of range` |
| `fulfill_excerpt` | `request_id: U64, excerpt_id: String, excerpt_hash: String, recorded_at: U64, quality_score: u8, signature: String` -> `Promise` | `unknown request`; status Open `request is not open`; `request deadline has passed`; `excerpt_id must be 1 to 64 chars of [A-Za-z0-9_-]`; `excerpt_hash must be 64 lowercase hex chars`; `quality_score must be 0 to 100`; `signature must be hex`; `signature must be 64 bytes`; `invalid signature`; recorded_at <= now `recorded_at is in the future`; recorded_at >= opened_at - window `recorded_at is outside the request window`; `quality score below buyer minimum`; `excerpt already paid for this request`; remaining >= price `budget exhausted` |
| `refund` | `request_id: U64` -> `Promise` | `unknown request`; `request already refunded`; now > deadline `deadline has not passed yet`; remaining > 0 `nothing to refund` |

On a paid excerpt: spent += price, paid_count += 1, store the payout, transfer price to seller, event `excerpt_paid`. If remaining < price (or paid_count hits 200) the status becomes `Exhausted` with event `request_exhausted`. `refund` works for Open or Exhausted after the deadline, sends `budget - spent` to the buyer, status `Refunded`, event `request_refunded` with `{request_id, buyer, amount}`.

Request record `KeywordRequest`: `id, buyer, query, window_seconds, price_per_excerpt, budget, spent, paid_count, min_quality, opened_at_ns, deadline_ns, status` (`Open | Exhausted | Refunded`). Payout record `ExcerptPayout`: `request_id, excerpt_id, excerpt_hash, recorded_at, quality_score, seller, paid, submitted_by, paid_at_ns`.
Views: `get_config` (v1 fields plus `default_window_seconds`), `get_request`, `get_requests(from_index?, limit?)`, `get_payouts(request_id)` in pay order, `is_paid(request_id, excerpt_id)`, `get_signing_message(request_id, excerpt_id, excerpt_hash, recorded_at, quality_score)`.

Excerpt hash: plain sha256 of the excerpt text, lowercase hex. Not HMAC. Only the hash goes on chain.

## 4. Agent side (`agent/src/v2/`, TypeScript)
- Parser: query to OR of AND groups (DNF), at most 16 groups and 8 terms per group, duplicates removed.
- Matcher: NFKC, lowercase, tokens are runs of letters and digits. A term matches when its tokens appear contiguously in the text tokens, so `Act` does not match `Actually`, and `"Clarity Act"` matches `Clarity-Act`.
- Sentences: split after `.`, `!` or `?` followed by whitespace. Excerpt id: `<segment_id>-s<sentence index>`.
- Feed: `sample-data/keyword-feed.json`, 8 SAMPLE DATA segments with `recorded_at` times around `replay_anchor` 2026-11-13T15:00:00Z. Replay shifts every time by `now - replay_anchor` so the demo looks live.
- Oracle v2: own key file `.keys/oracle-v2-testnet.json` (Bob creates it on the box), signs the message in section 3.

Expected matches for `NVIDIA OR (Clarity AND Act)`, window 3600, min quality 70, opened and checked at the anchor: `sd-r1-02-s2`, `sd-r2-01-s2`, `sd-r3-02-s2`, `sd-r3-02-s5`. Five minutes later `sd-r4-01-s1` joins. `sd-r1-01-s1` is outside the window, `sd-r2-02-s1` is below the bar (48), `sd-r3-01` has no match.

## 5. Tests
- Contract unit tests (`cargo test` in `contract-v2/`): every panic in section 3, the happy path, default and custom window, window edges, tampered recorded_at and score, a v1 domain signature, same excerpt on two requests, exhaustion with a remainder, refund of full budget, of a remainder, twice, and with nothing left.
- Sandbox tests (`integration-tests/market-v2.test.ts`, local near-sandbox): happy path pays the seller per excerpt, bad signature, out of window, low quality, double pay, budget exhaustion, refund.
- Parser and matcher unit tests (`agent/src/v2/*.test.ts`, node:test via tsx).
- Testnet demo (`scripts/demo-v2.ts`), run by Bob only: open a 0.05 NEAR request at 0.01 per excerpt, show the guardrail rejections, pay 5 excerpts until Exhausted, open a short request and refund it. Tx hashes to `demo-output/demo-v2-testnet-txs.json`.

## 6. Timeline (ET) and fallback
- Fri Nov 13 by 10 AM: OpenClaw session 3 done (all stages). 10 AM to 1 PM: Bob review, fixes, full test run.
- By 3 PM: Bob creates `market2.oralys-signal.testnet`, deploys, runs the testnet demo, records hashes.
- By 5 PM: README and docs final, scans pass. 6 PM hard cutoff: if v2 is not solid, we ship v1 (`publish` c466a59).
