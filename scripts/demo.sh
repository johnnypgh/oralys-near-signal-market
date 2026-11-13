#!/usr/bin/env bash
# Builds the contract and runs the end to end demo.
#   scripts/demo.sh                 local sandbox
#   NEAR_ACCOUNT_ID=<you>.testnet scripts/demo.sh testnet
set -euo pipefail
cd "$(dirname "$0")/.."
NETWORK="${1:-sandbox}"
if [ ! -f contract/target/near/oralys_signal_market.wasm ]; then
  (cd contract && cargo near build non-reproducible-wasm)
fi
[ -d node_modules ] || npm install
npx tsx scripts/demo.ts --network "$NETWORK"
