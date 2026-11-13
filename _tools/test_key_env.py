#!/usr/bin/env python3
"""NEAR_API_KEY must never be read. Only NEAR_AI_CLOUD_API_KEY is. No network."""
import asyncio
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import attest  # noqa: E402
import evaluate  # noqa: E402

FAKE = "sample-builders-value-KEYENV-0000"


def no_http(*args, **kwargs):
    raise AssertionError("no HTTP call expected")


class OtherKeyIgnoredTests(unittest.TestCase):
    def test_key_env_name(self):
        self.assertEqual(attest.KEY_ENV, "NEAR_AI_CLOUD_API_KEY")

    def test_model_mode_makes_no_http_call(self):
        feed = {"data_label": "SAMPLE DATA", "signals": []}
        policy = {"budget_near": "0.1", "min_quality": 70,
                  "max_price_near": "0.05", "topics": [], "ttl_seconds": 600}
        for extra in ([], ["--require-attestation"]):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "decisions.json"
                stdout, stderr = io.StringIO(), io.StringIO()

                def write(path, value):
                    Path(path).write_text(json.dumps(value), encoding="utf-8")

                fixtures = {evaluate.FEED: feed, evaluate.POLICY: policy}
                with (
                    patch.dict(os.environ, {"NEAR_API_KEY": FAKE}, clear=True),
                    patch.object(sys, "argv", ["evaluate.py", "--mode", "model", *extra]),
                    patch.object(evaluate, "OUT", str(out)),
                    patch.object(evaluate, "load_json", side_effect=fixtures.__getitem__),
                    patch.object(evaluate, "write_json", side_effect=write),
                    patch.object(urllib.request, "urlopen", side_effect=no_http),
                    patch.object(attest, "http_json", side_effect=no_http),
                    patch.object(attest, "save", side_effect=no_http),
                    redirect_stdout(stdout), redirect_stderr(stderr),
                ):
                    evaluate.main()
                text = out.read_text(encoding="utf-8")
                data = json.loads(text)
                self.assertEqual(data["mode"], "rules")
                self.assertEqual(data["fallback_reason"], "missing_api_key")
                for captured in (text, stdout.getvalue(), stderr.getvalue()):
                    self.assertNotIn(FAKE, captured)

    def test_attest_signature_makes_no_keyed_call(self):
        http = Mock(side_effect=no_http)
        with patch.dict(os.environ, {"NEAR_API_KEY": FAKE}, clear=True):
            result = attest.get_signature("sample", "ecdsa", http=http, sleep=Mock())
        http.assert_not_called()
        self.assertEqual(result["error_code"], "missing_key")
        self.assertNotIn(FAKE, json.dumps(result))

    def test_attest_preflight_sends_no_key(self):
        seen = []

        def http(url, *, data=None, headers=None):
            seen.append((url, dict(headers or {}), data))
            return {"model_attestations": [], "gateway_attestation": None}

        stdout = io.StringIO()
        with (
            patch.dict(os.environ, {"NEAR_API_KEY": FAKE}, clear=True),
            redirect_stdout(stdout),
        ):
            evidence = asyncio.run(attest.preflight(http=http))
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "near-ai-attestation.json"
                attest.save(evidence, output=path)
                written = "".join(
                    p.read_text(encoding="utf-8") for p in Path(tmp).rglob("*") if p.is_file()
                )
            attest.print_summary(evidence.audit)
        self.assertTrue(seen)
        for url, headers, data in seen:
            self.assertNotIn("authorization", {h.lower() for h in headers})
            self.assertNotIn(FAKE, url + json.dumps(headers) + str(data))
        self.assertNotIn(FAKE, written)
        self.assertNotIn(FAKE, stdout.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
