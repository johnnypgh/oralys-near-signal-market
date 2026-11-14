# 05_intents_quote (stretch): DRY quote for a USDC payment through NEAR Intents

model: none (script)

DRY QUOTES ONLY. NEAR Intents has no testnet. This stage sends `"dry": true` to the 1Click API, which
returns pricing with no deposit address. Nothing is signed, deposited or spent. Going further than a
dry quote is out of scope. Research notes: `notes/intents-testnet.md`.

## Inputs
- `_tools/intents_quote.py` (asset ids and placeholders are set there)
- `notes/intents-testnet.md`

## Process
1. Run `python3 -I _tools/intents_quote.py --amount-usdc 1`.
2. Read `amountIn`, `amountOut` and the fees in the output. The origin chain in the script is an example only.

## Outputs
- `stages/05_intents_quote/output/quote.json`

## Check
- `python3 -I _tools/intents_quote.py --check` prints `CHECK OK`: the request was dry and there is no deposit address.
