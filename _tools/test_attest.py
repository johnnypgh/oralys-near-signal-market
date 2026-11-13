#!/usr/bin/env python3
"""Offline SAMPLE DATA tests. No live HTTP or optional packages required."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent))
import attest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing fixtures are errors, not silent test skips.
        cls.raw = json.loads((FIXTURES / "report-glm-ecdsa.json").read_text())
        cls.fields = json.loads((FIXTURES / "quote-fields-glm-ecdsa.json").read_text())
        cls.nonce = (FIXTURES / "nonce-glm-ecdsa.txt").read_text().strip()

    def pairs(self):
        yield "gateway", self.raw["gateway_attestation"]
        for index, report in enumerate(self.raw["model_attestations"]):
            yield "model_{}".format(index), report

    def test_saved_quote_bindings(self):
        self.assertEqual(self.nonce.lower(), self.fields["nonce"])
        for label, report in self.pairs():
            with self.subTest(label=label):
                checks = attest.binding_checks(
                    report, self.fields["reports"][label], self.nonce, "ecdsa",
                )
                self.assertTrue(attest.all_pass(checks), checks)

    def test_tampered_nonce(self):
        nonce = ("00" if self.nonce[:2] != "00" else "01") + self.nonce[2:]
        for label, report in self.pairs():
            checks = attest.binding_checks(
                report, self.fields["reports"][label], nonce, "ecdsa",
            )
            self.assertTrue(checks["report_data_binds_nonce"].startswith("fail:"))
            self.assertTrue(checks["request_nonce_echo"].startswith("fail:"))

    def test_tampered_signer(self):
        for label, report in self.pairs():
            altered = {**report, "signing_address": "0x" + "00" * 20}
            checks = attest.binding_checks(
                altered, self.fields["reports"][label], self.nonce, "ecdsa",
            )
            self.assertTrue(checks["report_data_binds_signer"].startswith("fail:"))

    def test_compose_and_event_tampering(self):
        report = copy.deepcopy(self.raw["gateway_attestation"])
        info = attest.decoded(report["info"]["tcb_info"])
        report["info"]["tcb_info"] = {**info, "app_compose": info["app_compose"] + " "}
        checks = attest.binding_checks(
            report, self.fields["reports"]["gateway"], self.nonce, "ecdsa",
        )
        self.assertTrue(checks["mrconfigid_matches_app_compose"].startswith("fail:"))
        report["event_log"] = [{
            "imr": 3, "event_type": 1, "event": "tampered", "event_payload": "",
            "digest": "00" * 48,
        }]
        checks = attest.binding_checks(
            report, self.fields["reports"]["gateway"], self.nonce, "ecdsa",
        )
        self.assertTrue(checks["rtmr3_event_log_replay"].startswith("fail:"))

    def test_missing_dcap_has_no_quote_passes(self):
        with patch.object(attest.importlib, "import_module", side_effect=ImportError):
            result = asyncio.run(attest.verify_report(
                "gateway", self.raw["gateway_attestation"], self.nonce,
                "ecdsa", attest.MODEL, Mock(side_effect=AssertionError("network")),
            ))
        self.assertEqual(
            result["checks"]["dcap_quote_signature_and_collateral"],
            "not verified: dcap-qvl not installed",
        )
        for name in attest.QUOTE_CHECKS:
            if name in result["checks"]:
                self.assertNotEqual(result["checks"][name], "pass")
        self.assertFalse(result["verified"])

    @unittest.skip("Live DCAP collateral verification requires network")
    def test_live_dcap(self):
        pass

    @unittest.skip("Live NVIDIA NRAS verification requires network")
    def test_live_nras(self):
        pass


def synthetic_report(nonce, address, model=False):
    event = {"imr": 3, "event_type": 7, "event": "sample", "event_payload": "01"}
    digest = hashlib.sha384(struct.pack("<I", 7) + b":sample:\x01").digest()
    fields = {
        "report_data": (bytes.fromhex(address) + bytes(12) + bytes.fromhex(nonce)).hex(),
        "mr_config_id": (b"\x01" + hashlib.sha256(b"sample").digest() + bytes(15)).hex(),
        "rt_mr3": hashlib.sha384(bytes(48) + digest).hexdigest(),
        "td_attributes": bytes(8).hex(),
    }
    report = {
        "intel_quote": "00",
        "signing_algo": "ecdsa",
        "signing_address": "0x" + address,
        "request_nonce": nonce,
        "info": {"tcb_info": {"app_compose": "sample"}},
        "event_log": [event],
    }
    if model:
        report["model_name"] = attest.MODEL
        report["nvidia_payload"] = json.dumps({"nonce": nonce, "evidence": "sample"})
    return report, fields


class MockedPreflightTests(unittest.TestCase):
    def test_full_flow_uses_mocked_http_and_quote_verifier(self):
        nonce = "12" * 32
        gateway, gateway_fields = synthetic_report(nonce, "34" * 20)
        model, model_fields = synthetic_report(nonce, "56" * 20, True)
        fields = iter((gateway_fields, model_fields))

        async def verify(quote):
            self.assertEqual(quote, b"\0")
            value = next(fields)
            return Mock(status="UpToDate", to_json=lambda: json.dumps({"report": {"TD10": value}}))

        claims = attest.base64.urlsafe_b64encode(json.dumps({
            "x-nvidia-overall-att-result": True,
        }).encode()).decode().rstrip("=")
        http = Mock(side_effect=[
            {"gateway_attestation": gateway, "model_attestations": [model]},
            [["JWT", "sample." + claims + ".sample"]],
        ])
        with patch.object(attest.secrets, "token_hex", return_value=nonce), patch.object(
            attest.importlib, "import_module",
            return_value=Mock(get_collateral_and_verify=verify),
        ):
            evidence = asyncio.run(attest.preflight(http=http))
        self.assertEqual(evidence.audit["overall_verdict"], "verified")
        url = http.call_args_list[0].args[0]
        self.assertIn("signing_algo=ecdsa", url)
        self.assertIn("nonce=" + nonce, url)
        self.assertEqual(
            json.loads(http.call_args_list[1].kwargs["data"]),
            json.loads(model["nvidia_payload"]),
        )

    def test_missing_candidates(self):
        http = Mock(return_value={"gateway_attestation": {}})
        with patch.object(attest.importlib, "import_module", side_effect=ImportError):
            result = asyncio.run(attest.preflight(http=http))
        self.assertEqual(result.audit["overall_verdict"], "not verified")
        self.assertTrue(result.audit["checks"]["model_candidates_present"].startswith("fail:"))

    def test_gpu_nonce_prevents_post(self):
        http = Mock(side_effect=AssertionError("must not send"))
        checks = attest.gpu_checks({"nvidia_payload": {"nonce": "00" * 32}}, "01" * 32, http)
        self.assertTrue(checks["gpu_nonce"].startswith("fail:"))
        http.assert_not_called()


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.request = b'{"sample":true}'
        self.response = b'{"id":"sample-completion"}'
        self.evidence = attest.Preflight(attest.MODEL, "ecdsa", "12" * 32)
        self.evidence.finished = True
        self.evidence.audit["overall_verdict"] = "verified"
        self.evidence.reports.extend([
            {"label": "gateway", "model": None, "signing_algo": "ecdsa",
             "signing_address": "0x" + "34" * 20, "verified": True},
            {"label": "model_0", "model": attest.MODEL, "signing_algo": "ecdsa",
             "signing_address": "0x" + "56" * 20, "verified": True},
        ])

    def signature(self, kind="provider_tee"):
        text = attest.sha256(self.request) + ":" + attest.sha256(self.response)
        if kind == "provider_tee":
            text = attest.MODEL + ":" + text
        return {
            "text": text, "signature_kind": kind, "signing_algo": "ecdsa",
            "signing_address": "0x" + ("34" if kind == "gateway" else "56") * 20,
            "signature": "00" * 65,
        }

    def run_response(self, signature):
        return attest.verify_response(
            signature, self.request, self.response, attest.MODEL, self.evidence,
        )

    def test_provider_exact_match(self):
        with patch.object(attest, "verify_signature", return_value="pass") as crypto:
            result = self.run_response(self.signature())
        self.assertEqual(result["overall_verdict"], "verified")
        self.assertEqual(result["scope"], "provider_tee")
        crypto.assert_called_once()

    def test_gateway_only(self):
        with patch.object(attest, "verify_signature", return_value="pass"):
            result = self.run_response(self.signature("gateway"))
        self.assertEqual(result["overall_verdict"], "verified gateway-only")
        self.assertEqual(result["scope"], "gateway-only")

    def test_unknown_kind(self):
        for kind in (None, "unknown"):
            self.assertEqual(self.run_response(self.signature(kind))["overall_verdict"], "not verified")

    def test_signer_mismatch_and_duplicates(self):
        signature = self.signature()
        signature["signing_address"] = "0x" + "99" * 20
        self.assertTrue(self.run_response(signature)["checks"]["exactly_one_preflight_signer"].startswith("fail:"))
        self.evidence.reports.append(dict(self.evidence.reports[1]))
        self.assertTrue(self.run_response(self.signature())["checks"]["exactly_one_preflight_signer"].startswith("fail:"))

    def test_changed_bytes_and_algorithm(self):
        signature = self.signature()
        self.response += b"\n"
        self.assertTrue(self.run_response(signature)["checks"]["signed_text"].startswith("fail:"))
        signature = self.signature()
        signature["signing_algo"] = "ed25519"
        self.assertEqual(self.run_response(signature)["overall_verdict"], "not verified")

    def test_unavailable_and_saved_record_rejected(self):
        self.assertEqual(self.run_response({"error_code": "pending", "message": "pending"})["overall_verdict"], "not verified")
        self.evidence = self.evidence.audit
        self.assertEqual(self.run_response(self.signature())["overall_verdict"], "not verified")

    def test_optional_signature_packages_missing(self):
        for algo, size, sig_size in (("ecdsa", 20, 65), ("ed25519", 32, 64)):
            with patch.object(attest.importlib, "import_module", side_effect=ImportError):
                result = attest.verify_signature("sample", "00" * sig_size, "00" * size, algo)
            self.assertTrue(result.startswith("not verified:"))

    def test_mocked_crypto_apis(self):
        account = Mock()
        account.Account.recover_message.return_value = "0x" + "34" * 20
        messages = Mock()
        with patch.object(attest.importlib, "import_module", side_effect=[account, messages]):
            self.assertEqual(attest.verify_signature("sample", "00" * 65, "34" * 20, "ecdsa"), "pass")
        messages.encode_defunct.assert_called_once_with(text="sample")
        nacl = Mock()
        with patch.object(attest.importlib, "import_module", return_value=nacl):
            self.assertEqual(attest.verify_signature("sample", "00" * 64, "34" * 32, "ed25519"), "pass")
        nacl.VerifyKey.return_value.verify.assert_called_once_with(b"sample", bytes(64))

    def test_signature_http_retry_and_unavailable(self):
        missing = urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None)
        http = Mock(side_effect=[missing, self.signature()])
        sleep = Mock()
        with patch.dict(os.environ, {"NEAR_AI_CLOUD_API_KEY": "sample-test-value"}):
            result = attest.get_signature("sample/id", "ecdsa", http=http, sleep=sleep)
        self.assertEqual(result["signature_kind"], "provider_tee")
        self.assertEqual(http.call_count, 2)
        self.assertIn("/sample%2Fid?signing_algo=ecdsa", http.call_args.args[0])
        sleep.assert_called_once()
        with patch.dict(os.environ, {"NEAR_AI_CLOUD_API_KEY": "sample-test-value"}):
            unavailable = attest.get_signature(
                "sample", "ecdsa", http=Mock(return_value={"error_code": "pending", "message": "pending"}),
            )
        self.assertEqual(self.run_response(unavailable)["overall_verdict"], "not verified")

    def test_retry_exhaustion(self):
        missing = urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None)
        http = Mock(side_effect=missing)
        with patch.dict(os.environ, {"NEAR_AI_CLOUD_API_KEY": "sample-test-value"}):
            result = attest.get_signature("sample", "ed25519", http=http, attempts=2, sleep=Mock())
        self.assertEqual(http.call_count, 2)
        self.assertIn("error_code", result)


class AuditTests(unittest.TestCase):
    def test_size_limit_and_cli_check(self):
        evidence = attest.Preflight(attest.MODEL, "ecdsa", "12" * 32)
        evidence.audit["checks"] = {"report_fetch": "not verified: sample"}
        evidence.raw = {"sample": "data"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            with patch.object(attest, "RAW_LIMIT", 1):
                audit = attest.save(evidence, output=path)
            self.assertNotIn("path", audit["raw_reports"])
            with patch.object(attest, "OUTPUT", path), patch("builtins.print"):
                self.assertEqual(attest.main(["--check"]), 0)
                self.assertEqual(attest.main(["--check", "--require-attestation"]), 1)
                path.write_text("{}")
                self.assertEqual(attest.main(["--check"]), 1)

    def test_small_raw_report_saved(self):
        evidence = attest.Preflight(attest.MODEL, "ecdsa", "12" * 32)
        evidence.raw = {"sample": "data"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            audit = attest.save(evidence, output=path)
            raw = (path.parent / audit["raw_reports"]["path"]).read_bytes()
            self.assertEqual(attest.sha256(raw), audit["raw_reports"]["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
