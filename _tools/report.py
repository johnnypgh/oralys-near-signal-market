#!/usr/bin/env python3
"""Stage 04: write a plain summary of what was bought and why, from this run's files only.

Usage: python3 -I _tools/report.py [--check]
"""
import argparse
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fail, load_json, path  # noqa: E402

DECISIONS = "stages/02_evaluate/output/decisions.json"
RECEIPTS = "stages/03_settle/output/receipts.json"
OUT = "stages/04_report/output/report.md"


def build():
    d, r = load_json(DECISIONS), load_json(RECEIPTS)
    rec = {x["signal_id"]: x for x in r["receipts"]}
    p = d["policy"]
    spent = sum((Decimal(x["price_near"]) for x in r["receipts"] if x["status"] == "Fulfilled"), Decimal(0))
    who = "rules engine (no NEAR_AI_CLOUD_API_KEY set)" if d["mode"] == "rules" else f"{d['model']['model']} via {d['model']['base_url']}"
    lines = [
        "# Buyer agent run report",
        "",
        "SAMPLE DATA. Every signal in this run is made up for the demo.",
        "",
        f"- Network: {r['network']}",
        f"- Market contract: {r['contract']}",
        f"- Buyer: {r['buyer']}",
        f"- Seller payout account: {r['seller']}",
        f"- Decisions made by: {who}",
        f"- Policy: budget {p['budget_near']} NEAR, minimum quality {p['min_quality']}, price cap {p['max_price_near']} NEAR",
        f"- Spent: {spent} NEAR on {len(rec)} signals",
        "",
        "| Signal | Score | Price (NEAR) | Decision | Why | Request | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for x in d["decisions"]:
        e = rec.get(x["signal_id"])
        lines.append(
            f"| {x['signal_id']} | {x['quality_score']} | {x['price_near']} | {'buy' if x['buy'] else 'skip'} | {x['reason']} | "
            f"{'#' + e['request_id'] if e else ''} | {e['status'] if e else ''} |"
        )
    if r["network"] == "testnet":
        lines += ["", "## Transactions", ""]
        for e in r["receipts"]:
            lines.append(f"- {e['signal_id']}: open {e['links'][0]} , fulfill {e['links'][1]}")
    return "\n".join(lines) + "\n"


def check():
    text = open(path(OUT), encoding="utf-8").read()
    if "\u2014" in text or "\u2013" in text:
        fail("report contains an em or en dash")
    if "SAMPLE DATA" not in text:
        fail("report must say SAMPLE DATA")
    if text != build():
        fail("report does not match this run's decisions and receipts; re-run the stage")
    print(f"CHECK OK: {OUT} matches this run's files and follows the copy rules")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    os.makedirs(os.path.dirname(path(OUT)), exist_ok=True)
    with open(path(OUT), "w", encoding="utf-8") as f:
        f.write(build())
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
