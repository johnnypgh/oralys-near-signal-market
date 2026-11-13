#!/usr/bin/env python3
"""Stage 01: copy the SAMPLE DATA feed into stages/01_intake/output/feed.json after checking its labels.

Usage: python3 -I _tools/intake.py [--source sample-data/signal-feed.json] [--check]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fail, load_json, write_json  # noqa: E402

OUT = "stages/01_intake/output/feed.json"


def validate(feed):
    if not str(feed.get("notice", "")).startswith("SAMPLE DATA"):
        fail("feed notice must start with SAMPLE DATA")
    ids = set()
    for s in feed.get("signals", []):
        for k in ("signal_id", "label", "topic", "title", "quality_score", "price_near", "transcript"):
            if k not in s:
                fail(f"signal missing {k}: {s}")
        if s["label"] != "SAMPLE DATA":
            fail(f"{s['signal_id']} is not labeled SAMPLE DATA")
        if not s["transcript"].startswith("SAMPLE DATA."):
            fail(f"{s['signal_id']} transcript must start with 'SAMPLE DATA.'")
        if not (0 <= int(s["quality_score"]) <= 100):
            fail(f"{s['signal_id']} quality_score out of range")
        if s["signal_id"] in ids:
            fail(f"duplicate signal_id {s['signal_id']}")
        ids.add(s["signal_id"])
    if not ids:
        fail("feed has no signals")
    return len(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="sample-data/signal-feed.json")
    ap.add_argument("--check", action="store_true", help="only validate the stage output")
    a = ap.parse_args()
    if a.check:
        n = validate(load_json(OUT))
        print(f"CHECK OK: {OUT} has {n} SAMPLE DATA signals")
        return
    feed = load_json(a.source)
    n = validate(feed)
    write_json(OUT, feed)
    print(f"wrote {OUT} ({n} signals from {a.source})")


if __name__ == "__main__":
    main()
