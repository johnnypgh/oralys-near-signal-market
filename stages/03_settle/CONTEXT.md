# 03_settle: pay for the chosen signals on the market contract

model: none (script)

## Inputs
- `stages/02_evaluate/output/decisions.json`
- `stages/01_intake/output/feed.json`
- `_shared/policy.json`
- `_shared/network.md` (sandbox vs testnet, where keys live)
- `contract/target/near/oralys_signal_market.wasm` (build with `npm run build:contract` if missing)

## Process
1. Local: `npx tsx _tools/settle.ts --network sandbox` (starts a throwaway sandbox, deploys, settles, stops).
2. Testnet: `NEAR_ACCOUNT_ID=<account>.testnet npx tsx _tools/settle.ts --network testnet`.
3. For each buy, the buyer opens a request with the price in escrow, the sample oracle signs a fulfillment,
   and the contract checks the ed25519 signature and the score before paying the seller.

## Outputs
- `stages/03_settle/output/receipts.json` (request ids, status, tx hashes, explorer links on testnet)

## Check
- `python3 -I _tools/check_receipts.py` prints `CHECK OK`: every planned buy was fulfilled and has both tx hashes.
