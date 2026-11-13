#!/usr/bin/env bash
# Runs stages 01 to 04 (and the dry 05 quote) in order, stopping at the first failed check.
#   _tools/run_pipeline.sh                 local sandbox
#   NEAR_ACCOUNT_ID=<you>.testnet _tools/run_pipeline.sh testnet
set -euo pipefail
cd "$(dirname "$0")/.."
NETWORK="${1:-sandbox}"
[ -d node_modules ] || npm install
[ -f contract/target/near/oralys_signal_market.wasm ] || (cd contract && cargo near build non-reproducible-wasm)
echo "== 01_intake";       python3 -I _tools/intake.py;   python3 -I _tools/intake.py --check
echo "== 02_evaluate";     python3 -I _tools/evaluate.py; python3 -I _tools/evaluate.py --check
echo "== 03_settle";       npx tsx _tools/settle.ts --network "$NETWORK"; python3 -I _tools/check_receipts.py
echo "== 04_report";       python3 -I _tools/report.py;   python3 -I _tools/report.py --check
if [ "${SKIP_INTENTS_QUOTE:-0}" != "1" ]; then
  echo "== 05_intents_quote (dry)"; python3 -I _tools/intents_quote.py; python3 -I _tools/intents_quote.py --check
fi
