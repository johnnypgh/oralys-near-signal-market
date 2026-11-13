# Network and model settings

## Chain
- Local runs use a throwaway NEAR sandbox started by `_tools/settle.ts --network sandbox`.
- Testnet runs read the account from env `NEAR_ACCOUNT_ID` and its key from `~/.near-credentials/testnet/` (never from this repo).
- Contract source: `contract/src/lib.rs`. Built wasm: `contract/target/near/oralys_signal_market.wasm`.

## Model (stage 02 only)

- All data is SAMPLE DATA. NEAR is Oralys's home chain.
- Endpoint: NEAR AI Cloud, OpenAI compatible, base_url `https://cloud-api.near.ai/v1`.
- Model: `z-ai/glm-5.3-flash`. A provider_tee signature is expected, verified once: Nov 12, 7:12 PM ET, see notes/near-ai-run.md.
- Stage 02 can call the model when env `NEAR_AI_CLOUD_API_KEY` is set. Never write the key to a file or print it.
- A failed completion records `http_status` and the API error type label in the stage 02 output, never the message.
- `NEAR_API_KEY` is never read. On some machines it holds a different key, such as a NEAR Builders account key, which NEAR AI Cloud rejects.
- Before completion, stage 02 preflights the attestation report without a key. It then calls the model and checks the per-response signature using the completion id when a key is present.
- A provider_tee signature is the intended proof that the model TEE signed the exact request and response bytes. glm-5.3-flash returned a verified provider_tee signature on Nov 12, 7:12 PM ET.
- A verified gateway signature proves that the gateway signed the bytes, not that the model TEE produced them. It does not satisfy `--require-attestation`.
- Optional packages in `_tools/requirements-attest.txt` are used when installed. Missing packages are reported as not verified, never as passed.
- No key set: `_tools/evaluate.py` uses its deterministic rules engine instead, so tests and the demo run without a key.
- Without `--require-attestation`, unavailable attestation does not by itself discard usable model output. The guard still applies. With the flag, attestation failures fall back to rules.
- The harness and local files are outside the model TEE. One verified model reply is recorded in notes/near-ai-run.md.
