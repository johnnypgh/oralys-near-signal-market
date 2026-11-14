#!/usr/bin/env python3
"""Stage 05 (stretch): ask NEAR Intents 1Click for a DRY quote of a USDC payment into NEAR.

DRY ONLY. The request always sends "dry": true, so 1Click returns pricing but no deposit address.
Nothing is signed, nothing is deposited, nothing is spent. NEAR Intents has no testnet, so this
stage never goes further than a quote. Signing, depositing or executing a swap is out of scope.

Usage: python3 -I _tools/intents_quote.py [--amount-usdc 1] [--check]
Env (optional): INTENTS_RECIPIENT (NEAR account to receive), INTENTS_REFUND_TO (EVM address on the origin chain)
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fail, load_json, write_json  # noqa: E402

API = "https://1click.chaindefuser.com/v0/quote"
OUT = "stages/05_intents_quote/output/quote.json"
# Example payment origin only. NEAR is Oralys's home chain; a buyer could pay from any chain 1Click supports.
ORIGIN = "nep141:base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near"  # USDC on Base (example)
DEST = "nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1"  # native USDC on NEAR
# Placeholders: a dry quote creates no deposit address and moves no funds.
DEFAULT_RECIPIENT = "297c47802abdc05733c2a0662e4fb6e8cc92b3d8d1378524cc0e165817e01858"  # sha256 of a fixed phrase, no known key
DEFAULT_REFUND = "0x1111111111111111111111111111111111111111"


def build_request(amount_usdc):
    deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "dry": True,
        "swapType": "EXACT_INPUT",
        "slippageTolerance": 100,
        "originAsset": ORIGIN,
        "depositType": "ORIGIN_CHAIN",
        "destinationAsset": DEST,
        "amount": str(int(round(float(amount_usdc) * 1_000_000))),
        "recipient": os.environ.get("INTENTS_RECIPIENT", DEFAULT_RECIPIENT),
        "recipientType": "DESTINATION_CHAIN",
        "refundTo": os.environ.get("INTENTS_REFUND_TO", DEFAULT_REFUND),
        "refundType": "ORIGIN_CHAIN",
        "deadline": deadline,
    }


def check():
    d = load_json(OUT)
    if d["request"].get("dry") is not True:
        fail("request was not dry")
    q = d.get("response", {}).get("quote", {})
    if "depositAddress" in q:
        fail("response contains a deposit address; this stage must stay dry")
    if "amountOut" not in q:
        fail(f"no amountOut in response (http {d.get('http_status')})")
    print(f"CHECK OK: {OUT} dry quote, amountIn={q.get('amountIn')} amountOut={q.get('amountOut')} (USDC 6 decimals), no deposit address")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amount-usdc", default="1")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    body = build_request(a.amount_usdc)
    assert body["dry"] is True
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "oralys-signal-market/0.1 (dry quote)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, resp = r.status, json.load(r)
    except urllib.error.HTTPError as e:
        status, resp = e.code, {"error": e.read().decode(errors="replace")}
    write_json(OUT, {
        "note": "DRY QUOTE ONLY. No deposit address, no signing, no funds moved. NEAR Intents has no testnet.",
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "endpoint": API,
        "http_status": status,
        "request": body,
        "response": resp,
    })
    print(f"wrote {OUT} (http {status})")


if __name__ == "__main__":
    main()
