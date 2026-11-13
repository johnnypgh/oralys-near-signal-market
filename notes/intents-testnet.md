# Stage 05: NEAR Intents dry quote research

## Scope
NEAR is Oralys's home chain. Intents is a stretch payment route, not a required part of this entry.
NEAR Intents has no testnet and no plans for one, as referenced by [HACKATHON.md](https://nearhackathon.com/HACKATHON.md) Q-007 and SPEC section 9:
- FAQ: https://docs.near-intents.org/resources/faqs
- Quickstart warning: https://docs.near-intents.org/integration/distribution-channels/1click-api/quickstart/introduction

This stage is dry quote only. It does not execute a swap or provide a testnet swap demonstration.
The recorded quote used the live pricing API, but nothing was signed, deposited or spent.

## API and request
`_tools/intents_quote.py` sends `POST https://1click.chaindefuser.com/v0/quote`.
The request always sets `"dry": true`, which returns pricing without a deposit address.
- Quote docs: https://docs.near-intents.org/api-reference/oneclick/request-a-swap-quote
- OpenAPI: https://1click.chaindefuser.com/docs/v0/openapi.yaml

Find supported token asset ids with `GET https://1click.chaindefuser.com/v0/tokens`.
The script uses the following example route:
- Origin: USDC on Base, `nep141:base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near`.
- Destination: NEAR USDC, `nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1`.

The origin is an example payment starting point, not Oralys's home chain.
The request uses `EXACT_INPUT` and expresses the amount in USDC units with 6 decimals.

## Placeholders and headers
Default recipient: `297c47802abdc05733c2a0662e4fb6e8cc92b3d8d1378524cc0e165817e01858`.
The script describes this as a hash of a fixed phrase with no known key.
Default refund address: `0x1111111111111111111111111111111111111111`.
These are placeholders, not verified receiving or refund accounts.
Optional environment overrides are `INTENTS_RECIPIENT` and `INTENTS_REFUND_TO`.

The script sends `Content-Type: application/json`, `Accept: application/json`, and
`User-Agent: oralys-signal-market/0.1 (dry quote)`.
SPEC records Cloudflare error 1010 without a User-Agent header.
Without a JWT, an extra 0.25% fee applies according to the quickstart page. HACKATHON.md Q-006 gives 0.2%. The two sources differ; the dry quote output shows the actual fees for a given request.

## Recorded run
SPEC records one run on Nov 12 at about 5:57 PM ET:
- HTTP 201.
- `amountIn`: `1000000`.
- `amountOut`: `995521`.
- No deposit address. Nothing signed, deposited or spent.

These are recorded quote values, not a promise of future pricing or a completed payment.

## Run and check
From the repository root:
```sh
python3 -I _tools/intents_quote.py --amount-usdc 1
python3 -I _tools/intents_quote.py --check
```
The first command requests pricing and writes `stages/05_intents_quote/output/quote.json`.
Review `amountIn`, `amountOut`, and fees in that output.
The check requires `request.dry` to be true, rejects `depositAddress` in the response quote,
and requires `amountOut`. On success it prints `CHECK OK`.
It checks the saved artifact, not swap execution or settlement.

## Mainnet boundary
Any mainnet execution would need John's separate approval through Beans.
Signing, depositing funds, and executing a swap are out of scope for this entry.
