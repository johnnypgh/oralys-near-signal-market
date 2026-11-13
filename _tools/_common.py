"""Shared helpers for the stage tools. Python 3 standard library only."""
import json
import os
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def path(*parts):
    return os.path.join(ROOT, *parts)


def load_json(rel):
    with open(path(rel), encoding="utf-8") as f:
        return json.load(f)


def write_json(rel, data):
    p = path(rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def fail(msg):
    print(f"CHECK FAILED: {msg}")
    sys.exit(1)


def near(s):
    return Decimal(str(s))


def rules_decisions(feed, policy):
    """The deterministic buying rules from _shared/buying-policy.md."""
    remaining = near(policy["budget_near"])
    out = []
    for s in feed["signals"]:
        price = near(s["price_near"])
        if s["topic"] not in policy["topics"]:
            buy, reason = False, f"topic {s['topic']} is not on the list"
        elif s["quality_score"] < policy["min_quality"]:
            buy, reason = False, f"quality {s['quality_score']} is below the minimum of {policy['min_quality']}"
        elif price > near(policy["max_price_near"]):
            buy, reason = False, f"price {s['price_near']} NEAR is above the cap of {policy['max_price_near']}"
        elif price > remaining:
            buy, reason = False, f"price {s['price_near']} NEAR is more than the {remaining} NEAR left"
        else:
            buy, reason = True, f"quality {s['quality_score']} meets the minimum of {policy['min_quality']}"
            remaining -= price
        out.append({"signal_id": s["signal_id"], "buy": buy, "reason": reason})
    return out
