# Oralys Signal Market

## What it is

People are rewarded for recording what is said at conferences and events, where the latest on technology, policy and markets comes out. Oralys turns those recordings into transcript signals, and every transcript gets a Transcript Quality score from 0 to 100. Buyer agents pay per signal through an escrow contract on NEAR. The money is released only when the transcript meets the agent's quality bar. The platform, which is the seller account in this demo, collects the payment. Recorders are compensated afterward by the platform in tokens. They can swap the tokens to USDC or give them to agents, their own or others, who spend them in the marketplace.

Recorder compensation in tokens happens off contract and is not part of this demo. The contract pays the seller account and stops there.

Oralys Signal Market is the pay per signal escrow contract plus a buyer agent that pays for SAMPLE DATA transcript signals. Oralys gathers signal in real time, when it matters. NEAR is Oralys's home chain. Built during the hackathon window for the Agent Economy, Open Innovation and Privacy tracks. The private Oralys app is not part of this repo.

## How NEAR fits

The buyer deposits a budget into the NEAR contract. A seller oracle signs the signal's keyed transcript hash and quality score. The contract verifies the ed25519 signature on chain with `env::ed25519_verify` before releasing escrow to the seller. Transcripts never go on chain.

The contract itself enforces the buyer's minimum quality score. A signed score below the stored minimum fails with `quality score below buyer minimum`, and no payout is released. The signature binds the score, signal, contract and request. Expired open requests can be refunded to the buyer.

The contract emits NEP-297 style events for requests, fulfillment, refunds and signer changes. It is deployed on NEAR testnet.

The buyer agent checks budget, minimum quality, topic and price before opening a request. The shared policy sets a budget of 0.1 NEAR, minimum quality of 70 and price cap of 0.05 NEAR. These agent checks do not replace contract enforcement.

Stage 02 decides which signals the buyer agent buys. By default it uses the rules engine. With `NEAR_AI_CLOUD_API_KEY` set, it can ask `z-ai/glm-5.3-flash` on NEAR AI Cloud (`https://cloud-api.near.ai/v1`) for a recommendation on signal metadata only, never transcript text, and a guard reapplies the hard buying rules either way, so the model cannot buy anything the policy forbids.

Before any model call, `_tools/attest.py` fetches a fresh NEAR AI Cloud attestation report with a random nonce and checks it without an API key: the Intel TDX quote verifies with dcap-qvl (TCB UpToDate, debug off), the quote binds that nonce and the model's signing key, the measured configuration (MRCONFIGID) and RTMR3 event log match the quote, and NVIDIA's attestation service (NRAS) accepts the GPU evidence. On Nov 12, 2026, 7:12 PM ET all of these checks passed for the gateway report and the glm-5.3-flash model report. After a reply, stage 02 fetches the reply's signature and accepts it only if a `provider_tee` signer matches exactly one verified model report and the signature verifies over the exact request and response bytes.

Verified run, Nov 12, 2026, 7:12 PM ET, with `--require-attestation`: glm-5.3-flash answered stage 02 inside its TEE, and the reply's signature checked out. The signature kind was `provider_tee`, meaning the model TEE signed it, not only the gateway. It is an ecdsa signature over `model:sha256(request):sha256(response)` for the exact bytes sent and received, and it recovers to `0x3b753b4406613c5e70ae640508632b600424fa0c`, the signer of the one verified glm-5.3-flash attestation report from the same run. The model bought sample-001, 002 and 004 and skipped the rest, the same choices as the rules engine. Two earlier keyed runs that evening failed before any reply (first the wrong key, then an HTTP error whose status was not recorded) and fell back to rules. Details: [notes/near-ai-run.md](notes/near-ai-run.md).

### Check it yourself

Do: run `npm run test:sandbox`.
See: 9 passing tests, including a forged oracle signature rejected with `invalid signature` and a score below the buyer minimum rejected with `quality score below buyer minimum`.

Do: open the transaction links in the Testnet table below.
See: the payouts, the two rejected fulfillments and the refund on NEAR testnet.

Do: from the repo root, run `pip install -r _tools/requirements-attest.txt`, then `python3 -I _tools/attest.py --preflight-only`. No API key is needed.
See: a "Verified" list with the DCAP quote, nonce and signer binding, MRCONFIGID, RTMR3 and NVIDIA GPU checks for `z-ai/glm-5.3-flash`, and `Overall: verified`. Without the optional packages the same checks are listed under "Not verified" instead.

Do: run `python3 -I _tools/attest.py --check`.
See: the recorded Nov 12, 7:12 PM ET audit in `notes/near-ai-attestation.json` listed as Verified, including `signature_kind`, `signed_text`, `exactly_one_preflight_signer` and `signature_crypto`, then `Overall: verified` and `Scope: provider_tee`. This reads the record; checking a new reply yourself needs your own NEAR AI Cloud key in `NEAR_AI_CLOUD_API_KEY` and `python3 -I _tools/evaluate.py --mode model --require-attestation`.

Do: open `stages/02_evaluate/output/decisions.json`.
See: `mode: model`, `require_attestation: true`, and the model's reason for each of the six SAMPLE DATA signals.

## Repo map

This is an ICM folder workspace. Any harness that reads `AGENTS.md` can run it, including OpenClaw, Hermes, Claude Code and Cursor.

ICM method: Van Clief and McDermott, "Interpretable Context Methodology: Folder Structure as Agent Architecture" (arXiv:2603.16021). The icm-architect skill (MIT) is linked, not copied: https://github.com/RinDig/icm-architect

| Path | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Agent entry map and working rules |
| [CONTEXT.md](CONTEXT.md) | Pipeline inputs, outputs and checks |
| [stages/](stages/) | Intake, evaluation, settlement, reporting and dry quote |
| [_shared/](_shared/) | Buying policy, network settings and data rules |
| [_tools/](_tools/) | Pipeline scripts and checks |
| [contract/](contract/) | Rust escrow contract and unit tests |
| [agent/src/](agent/src/) | Buyer, seller oracle and NEAR helpers |
| [integration-tests/](integration-tests/) | Sandbox integration tests |
| [scripts/](scripts/) | Demo entry points |
| [sample-data/](sample-data/) | Made-up SAMPLE DATA feed |
| [notes/intents-testnet.md](notes/intents-testnet.md) | Intents dry quote scope and research |

When running stages through a harness, stop at each Check for person review as required by `AGENTS.md`.

## How to run

Prerequisites: Rust stable with cargo-near, Node with npm, and Python 3.

From the repo root:

```sh
npm install
npm run test:unit
npm run build:contract
npm run test:sandbox
npm run test:tools
npm run typecheck
npm run walk
```

The demo npm entry point is:

```sh
npm run demo
```

For an explicit local sandbox demo and pipeline run:

```sh
scripts/demo.sh sandbox
_tools/run_pipeline.sh sandbox
```

The pipeline stops at the first failed check. Stage 05 requests an external dry quote even when settlement uses sandbox. To omit that stage:

```sh
SKIP_INTENTS_QUOTE=1 _tools/run_pipeline.sh sandbox
```

### Testnet deployment

These commands are for an operator run outside OpenClaw. A testnet demo run submits transactions. It redeploys the contract only when the code on chain differs from the local build. Replace `<ACCOUNT>` with the account name before running.

```sh
cd contract && cargo near build non-reproducible-wasm && cd ..
```

The existing root account is `oralys-signal.testnet`. Creating a new account uses the testnet faucet and should be done only when a new account is needed:

```sh
near account create-account sponsor-by-faucet-service '<ACCOUNT>.testnet' autogenerate-new-keypair save-to-legacy-keychain network-config testnet create
```

With an existing account:

```sh
NEAR_ACCOUNT_ID='<ACCOUNT>.testnet' scripts/demo.sh testnet
NEAR_ACCOUNT_ID='<ACCOUNT>.testnet' _tools/run_pipeline.sh testnet
```

The demo creates or reuses the `market.`, `buyer.` and `seller.` sub-accounts, deploys the contract and runs the demo. The pipeline then runs against the deployed contract.

NEAR keys stay in `~/.near-credentials/`, with testnet keys under `~/.near-credentials/testnet/`. Oracle keys stay in `.keys/`, which is gitignored. The model key stays in the environment as `NEAR_AI_CLOUD_API_KEY`. Never print, log or commit them.

## Testnet

Deployed contract: `market.oralys-signal.testnet`

Explorer: https://testnet.nearblocks.io/address/market.oralys-signal.testnet

Final testnet demo run: Nov 12, 2026, 6:14 PM ET. 10 transactions, all SAMPLE DATA, testnet NEAR only. The contract already matched the current build (code hash `ACVxqCa67pvtCnBrvJzgFWndXbNQ8tF1zoVRgQSpKBFC`), so it was not redeployed.

| Step | Result | Transaction |
| --- | --- | --- |
| Buyer opens request #1 for sample-001 (score 88), 0.02 NEAR in escrow | ok | [6Jq6eoWr...](https://testnet.nearblocks.io/txns/6Jq6eoWrVYH6CBTLv1JNnaoDCUJ2PdebgT78osmSAQf3) |
| Oracle fulfills #1, contract verifies and pays the seller | ok | [8QhgXaHN...](https://testnet.nearblocks.io/txns/8QhgXaHN8zX4W37NcqidHP4N7DMqG8TB3umU7L37Mn28) |
| Buyer opens request #2 for sample-002 (score 74) | ok | [2ethFqpb...](https://testnet.nearblocks.io/txns/2ethFqpbdEBcFTR4bdFWSsee9Cb1zDdK9zNpbAnmbeeb) |
| Oracle fulfills #2, seller paid | ok | [5tCosw1L...](https://testnet.nearblocks.io/txns/5tCosw1Lrzk9GJ3EX2pXpwaijHX4CeVHxgwAjGawXG5z) |
| Buyer opens request #3 for sample-004 (score 91) | ok | [8GM64izR...](https://testnet.nearblocks.io/txns/8GM64izRcd9jmGU95v3Juzsnsv6r9Zj4gTmSxvmP5QTj) |
| Oracle fulfills #3, seller paid | ok | [2LSxyngZ...](https://testnet.nearblocks.io/txns/2LSxyngZUHGQYvKQUBa8hgawiZaUB9SBr5KofC4tWB6D) |
| Buyer opens stricter request #4 (minimum 80, 20 second deadline) | ok | [CwZ3gdjB...](https://testnet.nearblocks.io/txns/CwZ3gdjBFVpAs4GnKTJk8oUTHRMKhAVkc6SCqAaEp6gE) |
| Fulfillment signed by a key that is not the registered signer | rejected: invalid signature | [92yzx3mb...](https://testnet.nearblocks.io/txns/92yzx3mbKFArpVWcfWHW7hv1q8oGqQkKQEofr6kL1Fm9) |
| Genuine signature, score 74 below the minimum of 80 | rejected: quality score below buyer minimum | [GB16nbqJ...](https://testnet.nearblocks.io/txns/GB16nbqJgCTkGHUJ9F3ZA4Qb74fxFJFVrwoJXJAnPTmu) |
| Deadline passes, buyer refunded 0.02 NEAR | ok | [4XsmTRb2...](https://testnet.nearblocks.io/txns/4XsmTRb27cMrAq6tDfT2j6buBUtTyRrunSnPqqnGq773) |

The agent skipped sample-003 (52), sample-005 (39) and sample-006 (63) because they are below its minimum of 70. Full record: [notes/testnet-run.md](notes/testnet-run.md) and `notes/testnet-run.json`.

The demo writes every transaction hash and explorer link to `notes/testnet-run.json` and `notes/testnet-run.md` as it goes (sandbox runs write to `demo-output/`), plus a full log in `demo-output/demo-testnet.log`.

## Honest limits

- Contract settlement is testnet and local sandbox only. No real money.
- NEAR Intents has no testnet, as noted in [HACKATHON.md](https://nearhackathon.com/HACKATHON.md) Q-007 and the [Intents FAQ](https://docs.near-intents.org/resources/faqs). Stage 05 only requests a dry quote. It never signs, deposits or spends. See [the research notes](notes/intents-testnet.md).
- One verified model run is recorded. The completion id and request and response hashes are in the audit, but the reply body is not saved, so token usage and cost are not shown. The report and the reply are not proven to come from the same serving instance; NEAR AI docs say instances share one signing key. The rules engine path works without a model key.
- Attestation checks do not cover TLS connection binding or a measurement allowlist, and NVIDIA tokens are not signature checked locally.
- All demo data is made up and labeled SAMPLE DATA.
- Buyers do not pay storage for their request records. The contract balance covers it.
- Payout transfers have no callback to handle a seller account that has vanished.
- Each contract supports one oracle signer.
- Double fulfillment is covered by a unit test and a sandbox test.

## Disclosure

Oralys is an existing product. Only the NEAR integration in this repository was built during the hackathon window. The sample feed is made-up transcripts, labeled as sample data.

## Libraries and license

- near-sdk 5.30, Rust
- cargo-near 0.23
- near-api-js 7.5.3
- near-sandbox 0.3.5
- tsx
- TypeScript
- Python standard library
- dcap-qvl, eth-account and PyNaCl (optional, attestation checks only)
- AI coding tools

License: PolyForm Noncommercial License 1.0.0. See [LICENSE](LICENSE).

## v2: keyword requests

A buyer agent asks for keywords such as `NVIDIA OR (Clarity AND Act)` and pays for each matching excerpt from recordings within a buyer-selected time window. The deposit caps spending. Each accepted excerpt pays a fixed price to the platform's seller account, only if it meets the buyer's quality bar. NEAR is Oralys's home chain. All demo recordings and excerpts are SAMPLE DATA.

Recorders are compensated afterward by the platform in tokens. They can swap the tokens to USDC or give them to agents, their own or others, who spend them in the marketplace. This happens off contract and is not part of the demo.

Matching is done off chain and attested by the oracle's ed25519 signature, not proved on chain. The contract checks the signature, recording window, quality score, double pay and budget. Only the excerpt hash goes on chain, not the transcript. This is not a proof that the oracle matched the words correctly or scored quality correctly.

Tracks: Agent Economy, Open Innovation and Privacy.

Prize account: johnnyg.near

### Defaults

- Queries support AND, OR, parentheses and quoted phrases. Operators are case insensitive. No NOT, wildcards, commas or adjacent terms without an operator.
- Each request sets a fixed price per excerpt. The demo pays 0.01 NEAR; the minimum is 0.001 NEAR. The deposit is the total budget cap.
- Excerpts use the matching sentence plus one sentence on each side, capped at 400 characters. Drop context first, then cut at a word boundary.
- Every term of an AND group must match within one excerpt.
- Pay once per excerpt per request. Excerpts in the same segment do not overlap.
- The buyer sets the window: default 3600 seconds, allowed 60 to 604800 seconds (7 days).
- The main demo uses a 0.05 NEAR deposit, quality minimum 70 and a 600 second deadline. A second request has a 20 second deadline for the refund example.

### Run v2 locally

With dependencies already installed, Rust and cargo-near available:

```sh
npm run test:unit:v2
npm run build:contract:v2
npm run test:agent:v2
npm run test:sandbox:v2
npx tsc --noEmit
npm run demo:v2 -- --network sandbox
python3 -I _tools/links.py
```

The sandbox uses throwaway keys in memory. Build the v2 wasm first. The demo replays SAMPLE DATA with its anchor 300 seconds in the past, checks forged-signature, out-of-window, low-quality and double-pay rejections, pays five excerpts until Exhausted, then pays one excerpt on a short request and refunds the remainder. It fails if an expected result is missing. Logs and transaction hashes are saved after each step to `demo-output/demo-v2-sandbox.log` and `demo-output/demo-v2-sandbox-txs.json`, including partial results on failure.

### v2 testnet operator run

The operator runs this outside OpenClaw. The v2 script never creates testnet accounts, deploys a contract or creates oracle keys. It uses the existing deployment named by `MARKET2_ID`, default `market2.oralys-signal.testnet`, and checks its registered seller and oracle public key. Pass existing NEAR CLI JSON account files and an existing v2 oracle JSON file by path; do not paste key contents into commands or logs.

```sh
npx tsx scripts/demo-v2.ts --network testnet --buyer-key <existing-buyer-file> --seller-key <existing-seller-file> --oracle-key <existing-v2-oracle-file>
```

The testnet run submits payments and refund transactions using those existing accounts. It is not a read-only dry run. Results go only to `demo-output/demo-v2-testnet.log` and `demo-output/demo-v2-testnet-txs.json`. Set `NEAR_RPC_URL` to change the RPC, default https://test.rpc.fastnear.com. The v1 demo and its deployment flow are unchanged.

### v2 testnet run

Run Fri Nov 13, 2026, 12:19 AM ET on testnet, SAMPLE DATA only. Contract [market2.oralys-signal.testnet](https://testnet.nearblocks.io/address/market2.oralys-signal.testnet), code hash `GkDfZJkTx3EqgVpfUWLYYBadvenGi3Fx6biYJetfsxzQ`, seller `seller.oralys-signal.testnet`, buyer `buyer.oralys-signal.testnet`. Request `NVIDIA OR (Clarity AND Act)`, window 3600 seconds, 0.01 NEAR per excerpt, 0.05 NEAR deposit, quality minimum 70. Read back from the contract after the run: request 0 is Exhausted with 5 excerpts paid and 0.05 NEAR spent; request 1 is Refunded with 1 excerpt paid and 0.04 NEAR returned to the buyer. Record: [notes/testnet-run-v2.md](notes/testnet-run-v2.md).

| Step | Result | Tx |
| --- | --- | --- |
| create market2.oralys-signal.testnet, funded 2.3 NEAR from oralys-signal.testnet | ok | [7umU63b9qN](https://testnet.nearblocks.io/txns/7umU63b9qN4RR9hu1mBqj6SmEe3AfGCGqwyZcrKfHX6X) |
| deploy contract-v2 wasm and init new(owner, seller, signer) | ok | [ESvfnuxWY1](https://testnet.nearblocks.io/txns/ESvfnuxWY1ytpJ69WQpW1eHRt55eRcLsRVZPojXroZHz) |
| Open request with 600 second deadline | ok | [BvYm3SQQ7z](https://testnet.nearblocks.io/txns/BvYm3SQQ7z7t9qQn1jMV2u84FXSCTGePrKp2RwdFYZ3n) |
| Forged signature | rejected, invalid signature | [DTdGpbrvf3](https://testnet.nearblocks.io/txns/DTdGpbrvf3EZT4LoSuaSsG22emrhUwqMTZx8EsQK3hiz) |
| Out of window | rejected, recorded_at is outside the request window | [AmkxihxGkB](https://testnet.nearblocks.io/txns/AmkxihxGkBq73GXgx6VTRAg23KCs5qNr23fsadg4FYhC) |
| Low quality | rejected, quality score below buyer minimum | [J4z6zvoeJp](https://testnet.nearblocks.io/txns/J4z6zvoeJpZrKzoqBaa9D9TAasJw1xKRLiMVVoKeoetz) |
| Pay sd-r1-02-s2 | ok | [9jTJ1gokyG](https://testnet.nearblocks.io/txns/9jTJ1gokyGXEDn5Zgzi9RgjzEdVsc777tjKUQo25Vpbr) |
| Double pay | rejected, excerpt already paid for this request | [HRnpHwtwpm](https://testnet.nearblocks.io/txns/HRnpHwtwpmneRV8cvGiEq9iVUsNT3f3XQz69iZpiMMtm) |
| Pay sd-r2-01-s2 | ok | [96HrNvRgJg](https://testnet.nearblocks.io/txns/96HrNvRgJgNWDduhrx5YbWW2nCP32MDTBSifz38igcev) |
| Pay sd-r3-02-s2 | ok | [6w56ePCpRS](https://testnet.nearblocks.io/txns/6w56ePCpRSq3HzyjvLfUoMoGkuygFp68Vp2zDkmTx5CM) |
| Pay sd-r3-02-s5 | ok | [Hpd3gJyjcu](https://testnet.nearblocks.io/txns/Hpd3gJyjcutjkatFQavyhCfn3pCAK5KXEvy9DVQvkU76) |
| Pay sd-r4-01-s1 | ok | [289gEUdBLs](https://testnet.nearblocks.io/txns/289gEUdBLsDko6mdapwJukEC28equ2tMnZ8zqQcikvT4) |
| Open request with 20 second deadline | ok | [9Zk1iX78QM](https://testnet.nearblocks.io/txns/9Zk1iX78QMsHkao7RUeJSXRPruM8BEHbYNryj5iypic7) |
| Pay one excerpt on short request | ok | [HskNotrmzz](https://testnet.nearblocks.io/txns/HskNotrmzzdFzzxermuEmocaZQdMJYQVW7P2DRaZgHaL) |
| Refund after deadline | ok | [CEs5omy2JX](https://testnet.nearblocks.io/txns/CEs5omy2JXD7ysXp8ocTQ266BvUusc9c22WLSYm6dWFo) |

Tests run on the box Nov 13, 2026, about 12:20 AM ET: contract-v2 66 unit tests passed, v1 contract 18 passed, v2 sandbox 9 of 9 passed (8 cases plus the suite), v2 agent tests 45 of 45 passed, `npx tsc --noEmit` clean.

### v2 oracle and the TEE run

The v2 oracle does not use the model step. Query parsing, matching and excerpt building are plain TypeScript rules in `agent/src/v2/`, and the quality score comes from the SAMPLE DATA feed. The verified NEAR AI Cloud TEE run on Nov 12 covered only the v1 stage 02 buying decision. It did not cover v2 matching, so v2 makes no TEE claim.
