#!/usr/bin/env python3
"""Unit tests for the stage tools (no network). Usage: python3 -I _tools/test_tools.py"""
import importlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_json, rules_decisions  # noqa: E402
import evaluate  # noqa: E402
import intents_quote  # noqa: E402

FEED = load_json("sample-data/signal-feed.json")
POLICY = load_json("_shared/policy.json")


class RulesTest(unittest.TestCase):
    def test_rules_follow_policy(self):
        d = {x["signal_id"]: x for x in rules_decisions(FEED, POLICY)}
        self.assertTrue(d["sample-001"]["buy"])
        self.assertFalse(d["sample-003"]["buy"])  # 52 < 70
        self.assertFalse(d["sample-005"]["buy"])  # 39 < 70

    def test_budget_is_never_exceeded(self):
        tight = {**POLICY, "budget_near": "0.03"}
        buys = [x for x in rules_decisions(FEED, tight) if x["buy"]]
        self.assertEqual(len(buys), 1)


class GuardTest(unittest.TestCase):
    def test_guard_blocks_model_buy_that_rules_forbid(self):
        rules = rules_decisions(FEED, POLICY)
        model = [
            {"signal_id": x["signal_id"], "buy": True, "reason": "model says yes"}
            for x in rules
        ]
        out = {x["signal_id"]: x for x in evaluate.guard(model, rules)}
        self.assertFalse(out["sample-005"]["buy"])
        self.assertIn("guard overrode", out["sample-005"]["source"])
        self.assertTrue(out["sample-001"]["buy"])

    def test_guard_fills_missing_answers_from_rules(self):
        rules = rules_decisions(FEED, POLICY)
        out = evaluate.guard([], rules)
        self.assertEqual([x["buy"] for x in out], [x["buy"] for x in rules])

    def test_model_may_skip_an_allowed_signal(self):
        rules = rules_decisions(FEED, POLICY)
        model = [
            {"signal_id": "sample-001", "buy": False, "reason": "already have one"}
        ]
        out = {x["signal_id"]: x for x in evaluate.guard(model, rules)}
        self.assertFalse(out["sample-001"]["buy"])


class IntentsTest(unittest.TestCase):
    def test_quote_request_is_always_dry(self):
        self.assertIs(intents_quote.build_request("1")["dry"], True)
        self.assertEqual(intents_quote.build_request("2.5")["amount"], "2500000")


def load_tests(loader, tests, pattern):
    directory = Path(__file__).resolve().parent
    for path in sorted(directory.glob("test_*.py")):
        if path.stem == "test_tools":
            continue
        tests.addTests(loader.loadTestsFromModule(importlib.import_module(path.stem)))
    return tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
