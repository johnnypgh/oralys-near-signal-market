# NEAR AI Cloud keyed runs, stage 02 (SAMPLE DATA)

Command for both runs:
`python -I _tools/evaluate.py --mode model --require-attestation`
(Python venv with dcap-qvl, eth-account and pynacl installed.)
Model: `z-ai/glm-5.3-flash`, signing algorithm ecdsa. Three completions were
authorized in total and three runs were made. Run 3 is the verified one.

## Run 3: Nov 12, 2026, 7:12:26 PM ET to 7:12:33 PM ET (verified)

Key: env `NEAR_AI_CLOUD_API_KEY`, read in a fresh shell. It was the same key
value as run 2 (compared on the box, never printed). The cause of the run 2
error was not recorded; the tool now logs the HTTP status and error type of a
failed completion.

1. Preflight, no key used: fresh nonce
   `85ad4e9f1a597e036aa737c862b01d4ecfa1b852e525234720c984257a8e5ac5`. Every
   check passed for the gateway report and the one glm-5.3-flash model
   report: Intel TDX quote (dcap-qvl, TCB UpToDate, debug off), nonce and
   signer binding in report_data, MRCONFIGID against app_compose, RTMR3 event
   log replay, NVIDIA NRAS GPU result.
2. Completion: one request, one reply. Completion id
   `dfba4117364049a983056dc43808420f`. SHA-256 of the exact request body
   `2ebcc3969cc596dd15ab66ef036a16db1ec44737b26f46f5b8de3d4f1a141599`, of the
   exact response body
   `d65e896e4b3098011274aef7a65a52b4078002689f041afa4b28c599c800da17`.
3. Response signature, all checks passed:
   - signature kind `provider_tee` (signed by the model TEE, not only the
     gateway)
   - algorithm ecdsa, same as the preflight
   - signed text equals `model:sha256(request):sha256(response)` for these
     exact bytes
   - the signer matches exactly one verified preflight model report, model
     signer `0x3b753b4406613c5e70ae640508632b600424fa0c`
   - the ecdsa signature recovers to that signer
4. Overall verdict: verified, scope provider_tee. Stage 02 output:
   `mode: model`. The guard reapplied the hard rules. The model bought
   sample-001, 002 and 004 and skipped 003, 005 and 006, the same choices as
   the rules engine.
5. Usage and cost: the tool does not save the reply body, so no token usage
   or cost is recorded here.

Stage 04 was regenerated from this stage 02 output. Its receipts come from
the earlier sandbox settlement of the same three signals; settlement was not
re-run.

Files: `notes/near-ai-attestation.json` (audit),
`notes/near-ai-attestation-reports/bd5c36c3...json` (raw report),
`stages/02_evaluate/output/decisions.json` (stage 02 output, model).

## Run 2: Nov 12, 2026, 7:08:41 PM ET to 7:08:42 PM ET

Key: env `NEAR_AI_CLOUD_API_KEY`.

1. Preflight, no key used: fresh nonce, every check passed for the gateway
   report and the one glm-5.3-flash model report. That covers the Intel TDX
   quote (dcap-qvl, TCB UpToDate, debug off), nonce and signer binding in
   report_data, MRCONFIGID against app_compose, RTMR3 event log replay, and
   the NVIDIA NRAS GPU result. Model signer:
   `0x3b753b4406613c5e70ae640508632b600424fa0c` (same as run 1).
2. Completion: the request was sent and NEAR AI Cloud answered with an HTTP
   error. No reply and no completion id came back. The tool at that time did
   not record the status code. If it was a 5xx, the tool retries once, so
   this run sent one or two requests.
3. After the run, one keyed signature lookup for a made up id returned
   HTTP 404 "Signature not found", not 401. So the key itself is accepted.
4. Signature check: not reached. provider_tee did not come back. No signer
   match and no signature verification happened.
5. Fallback: stage 02 used the rules engine (`fallback_reason: http_error`).

Since this run, `_tools/evaluate.py` records the HTTP status code and the
API's short error type label (never the message) in the stage 02 output,
so the next run will show why a completion failed.

Files: `notes/near-ai-attestation-run2.json` (audit),
`notes/near-ai-attestation-reports/f9b5036b...json` (raw report). Its stage
02 output (rules) was replaced by run 3.

## Run 1: Nov 12, 2026, 6:55:29 PM ET to 6:55:30 PM ET

Preflight passed the same checks. The completion was rejected with HTTP 401.
A signature lookup with the same key returned "Invalid or expired API key".
At the time the tools read env `NEAR_API_KEY`, which on the machine used for that run held a
NEAR Builders account key, not a NEAR AI Cloud key. The tools now read
`NEAR_AI_CLOUD_API_KEY` only and never `NEAR_API_KEY`.

Files: `notes/near-ai-attestation-run1.json`,
`notes/near-ai-attestation-reports/30c977da...json`.

## Not claimed

- No TLS binding, no measurement allowlist, NVIDIA tokens not signature
  checked locally.
- The report and the completion are not proven to come from the same
  serving instance; NEAR AI docs say instances share one signing key.
