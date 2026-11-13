#!/usr/bin/env python3
"""Stage 03 check: every planned buy has a receipt, was fulfilled, and has both tx hashes.

Usage: python3 -I _tools/check_receipts.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fail, load_json  # noqa: E402

DECISIONS = "stages/02_evaluate/output/decisions.json"
RECEIPTS = "stages/03_settle/output/receipts.json"


def main():
    d, r = load_json(DECISIONS), load_json(RECEIPTS)
    planned = [x["signal_id"] for x in d["decisions"] if x["buy"]]
    got = {x["signal_id"]: x for x in r["receipts"]}
    if sorted(planned) != sorted(got):
        fail(f"planned {planned} but receipts cover {sorted(got)}")
    for sid, x in got.items():
        if x["status"] != "Fulfilled":
            fail(f"{sid} status {x['status']} ({x.get('fulfill_error')})")
        if not x["open_tx"] or not x["fulfill_tx"]:
            fail(f"{sid} is missing a tx hash")
    print(f"CHECK OK: {RECEIPTS} network={r['network']} {len(got)} fulfilled on {r['contract']}")


if __name__ == "__main__":
    main()
