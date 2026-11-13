# 02_evaluate: decide which signals to buy

model: z-ai/glm-5.3-flash, NEAR AI Cloud, provider_tee signature expected, verified once: Nov 12, 7:12 PM ET, see notes/near-ai-run.md.
Base URL: https://cloud-api.near.ai/v1. Key from env NEAR_AI_CLOUD_API_KEY only. NEAR_API_KEY is never read.
No key set: model: none (script), the rules engine in `_tools/_common.py` decides.
All data is SAMPLE DATA. NEAR is Oralys's home chain.

## Inputs

- `stages/01_intake/output/feed.json`
- `_shared/policy.json` (budget, minimum quality, price cap, topics)
- `_shared/buying-policy.md` (how the policy is applied)
- `_shared/network.md` (model settings)
- `_tools/attest.py`
- `_tools/requirements-attest.txt` (optional verification packages)

## Process

1. Run `python3 -I _tools/evaluate.py`. Auto mode uses the model when
   NEAR_AI_CLOUD_API_KEY is set, otherwise rules. Force a path with `--mode rules`
   or `--mode model`. Add `--require-attestation` to require a verified
   provider_tee response. NEAR_AI_SIGNING_ALGO defaults to ecdsa.
2. Preflight: fetch and check the attestation report without a key, before
   sending the completion. Retain the live evidence for response verification.
   Required attestation fails closed if preflight is not verified.
3. Completion: send signal metadata only, never transcript text. Retain the
   exact request body bytes and raw response bytes, without reserialization.
4. Signature check: read the completion id, fetch its signature, and verify
   its binding to those bytes, the model and the preflight signer. Save the
   audit even when verification fails, where possible. Only `verified` with
   provider_tee scope satisfies required attestation. `verified gateway-only`
   proves gateway signing, not model TEE signing.
5. Guard: strictly parse the model decisions and reapply the hard rules.
   The model cannot buy a signal the policy forbids.
6. Fallback: model HTTP, parsing and schema errors use the rules engine.
   Required attestation failures use `fallback_reason: attestation_error`.
   Without required attestation, missing or gateway-only signatures do not
   by themselves discard model output. Missing optional packages are reported
   as not verified, never as passed.
7. Review `stages/02_evaluate/output/decisions.json`. Edit a reason if unclear,
   but do not flip a decision by hand. Never write or print the key.

## Outputs

- `stages/02_evaluate/output/decisions.json`
- notes/near-ai-attestation.json, written by a model or preflight run into the existing `notes/` folder
- `notes/near-ai-attestation-reports/` when the audit includes saved reports.
  Authentication text is removed before persistence. Report hashes describe
  the saved, sanitized reports; response verification uses original wire bytes.

Rules-only runs do not create a new attestation audit. Check the audit timestamp
and completion id before treating an existing file as evidence for a run.

## Check

- `python3 -I _tools/evaluate.py --check` checks coverage, allowed buys and budget.
- `python3 -I _tools/attest.py --check` re-reads and validates the saved audit.
- When evaluation used `--require-attestation`, run
  `python3 -I _tools/attest.py --check --require-attestation`.
  This fails unless the saved overall verdict is exactly `verified`.
  The existing attestation CLI requires this explicit flag; it does not
  automatically enforce the saved `require_attestation` field.
- `python3 -I _tools/test_tools.py` includes rules, guard, intents, model HTTP,
  attestation and secret leak tests. All model and signature HTTP is mocked.

A person reviews the buy list before any later spending step.
