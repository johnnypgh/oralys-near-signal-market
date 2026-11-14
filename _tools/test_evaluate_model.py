#!/usr/bin/env python3
"""SAMPLE DATA model, attestation wiring and leak tests. All HTTP is mocked."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import AsyncMock, mock_open, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_json, rules_decisions  # noqa: E402
import attest  # noqa: E402
import evaluate  # noqa: E402

FEED = load_json("sample-data/signal-feed.json")
POLICY = load_json("_shared/policy.json")


class ModelTest(unittest.TestCase):
    FAKE_KEY = "sk-FAKE-LEAKCHECK-0000"

    def setUp(self):
        self.rules = rules_decisions(FEED, POLICY)
        self.feed = {
            **FEED,
            "signals": [
                {**signal, "transcript": "PRIVATE_TRANSCRIPT_SENTINEL"}
                for signal in FEED["signals"]
            ],
        }

    def reply(self, decisions=None, content=None):
        if content is None:
            content = json.dumps({
                "decisions": self.rules if decisions is None else decisions,
            })
        return io.BytesIO(json.dumps({
            "id": "sample-completion",
            "choices": [{"message": {"content": content}}],
        }).encode("utf-8"))

    def http_error(self, status):
        return urllib.error.HTTPError(
            "https://example.invalid/chat/completions",
            status,
            self.FAKE_KEY,
            {},
            io.BytesIO(b""),
        )

    def evidence(self, verified=False):
        evidence = attest.Preflight(evaluate.MODEL, "ecdsa", "00" * 32)
        evidence.finished = True
        evidence.audit["checks"]["sample"] = (
            "pass" if verified else "not verified: sample preflight"
        )
        if verified:
            evidence.audit["overall_verdict"] = "verified"
        return evidence

    def result(self, kind="provider_tee"):
        return {
            "checks": {"sample_signature": "pass"},
            "signature_kind": kind,
            "scope": "provider_tee" if kind == "provider_tee" else "gateway-only",
            "overall_verdict": (
                "verified" if kind == "provider_tee" else "verified gateway-only"
            ),
        }

    def run_main(
        self, effects=(), mode="model", key=True, required=False,
        preflight_ok=False, verification=None,
    ):
        argv = ["evaluate.py", "--mode", mode]
        if required:
            argv.append("--require-attestation")
        env = {"NEAR_AI_CLOUD_API_KEY": self.FAKE_KEY} if key else {}
        captured = io.StringIO()
        errors = io.StringIO()
        evidence = self.evidence(preflight_ok)
        self.saved_evidence = evidence

        def read_fixture(path):
            return {
                evaluate.FEED: self.feed,
                evaluate.POLICY: POLICY,
            }[path]

        verify_options = (
            {"return_value": verification}
            if verification is not None
            else {"wraps": attest.verify_response}
        )
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(sys, "argv", argv),
            patch.object(evaluate, "load_json", side_effect=read_fixture),
            patch.object(evaluate, "write_json") as write,
            patch("builtins.open", mock_open(read_data="SAMPLE DATA rules")),
            patch.object(
                evaluate.urllib.request, "urlopen", side_effect=effects,
            ) as urlopen,
            patch.object(
                attest, "preflight", new=AsyncMock(return_value=evidence),
            ) as preflight,
            patch.object(
                attest, "get_signature",
                return_value={"error_code": "sample_unavailable"},
            ) as signature,
            patch.object(attest, "verify_response", **verify_options) as verify,
            patch.object(attest, "save") as save,
            patch.object(evaluate, "guard", wraps=evaluate.guard) as guarded,
            redirect_stdout(captured),
            redirect_stderr(errors),
        ):
            evaluate.main()

        self.preflight = preflight
        self.signature = signature
        self.verify = verify
        self.save = save
        write.assert_called_once()
        self.assertEqual(write.call_args.args[0], evaluate.OUT)
        output = write.call_args.args[1]
        guarded.assert_called_once()
        for text in (json.dumps(output), captured.getvalue(), errors.getvalue()):
            self.assertNotIn(self.FAKE_KEY, text)
            self.assertNotIn("Bearer", text)
        return output, urlopen

    def assert_fallback(self, output, reason):
        self.assertEqual(output["mode"], "rules")
        self.assertIsNone(output["model"])
        self.assertEqual(output["fallback_reason"], reason)
        self.assertEqual(
            [d["buy"] for d in output["decisions"]],
            [r["buy"] for r in self.rules],
        )
        self.assertTrue(all(d["source"] == "rules" for d in output["decisions"]))

    def test_good_response_and_request_contract(self):
        response = self.reply()
        raw = response.getvalue()
        output, urlopen = self.run_main([response])
        self.assertEqual(output["mode"], "model")
        self.assertNotIn("fallback_reason", output)
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 60})
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            f"{evaluate.BASE_URL.rstrip('/')}/chat/completions",
        )
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer " + self.FAKE_KEY)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["x-no-aliasing"], "true")
        self.assertEqual(headers["accept-encoding"], "identity")
        self.assertIsInstance(request.data, bytes)
        body = json.loads(request.data)
        self.assertIs(body["stream"], False)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["model"], evaluate.MODEL)
        self.assertNotIn(b"PRIVATE_TRANSCRIPT_SENTINEL", request.data)
        self.assertNotIn(self.FAKE_KEY.encode(), request.data)
        self.preflight.assert_awaited_once_with(evaluate.MODEL, "ecdsa")
        self.signature.assert_called_once_with("sample-completion", "ecdsa")
        self.assertIs(self.verify.call_args.args[1], request.data)
        self.assertEqual(self.verify.call_args.args[2], raw)
        self.save.assert_called_once()
        self.assertEqual(self.save.call_args.kwargs["completion_id"], "sample-completion")

    def test_malformed_json(self):
        output, urlopen = self.run_main([self.reply(content='{"decisions":')])
        self.assert_fallback(output, "parse_error")
        self.assertEqual(urlopen.call_count, 1)

    def test_json_must_be_the_whole_content(self):
        for content in (
            'prefix {"decisions": []}',
            '{"decisions": []} trailing',
            '```json\n{"decisions": []}\n```',
            '{"decisions": []} {"decisions": []}',
        ):
            with self.subTest(content=content):
                output, _ = self.run_main([self.reply(content=content)])
                self.assert_fallback(output, "parse_error")

    def test_missing_field(self):
        decision = {"signal_id": "sample-001", "buy": True}
        output, _ = self.run_main([self.reply(decisions=[decision])])
        self.assert_fallback(output, "schema_error")

    def test_invalid_schema(self):
        invalid = [
            [],
            {},
            {"decisions": {}},
            {"decisions": [None]},
            {"decisions": [{"signal_id": 1, "buy": True, "reason": "sample"}]},
            {"decisions": [{"signal_id": "sample-001", "buy": 1, "reason": "sample"}]},
            {"decisions": [{"signal_id": "sample-001", "buy": "false", "reason": "sample"}]},
            {"decisions": [{"signal_id": "sample-001", "buy": True, "reason": None}]},
        ]
        for value in invalid:
            with self.subTest(value=value):
                output, _ = self.run_main([self.reply(content=json.dumps(value))])
                self.assert_fallback(output, "schema_error")

    def test_unknown_and_duplicate_signal_ids(self):
        unknown = {"signal_id": "unknown", "buy": True, "reason": "sample"}
        for decisions in ([unknown], [self.rules[0], self.rules[0]]):
            with self.subTest(decisions=decisions):
                output, _ = self.run_main([self.reply(decisions=decisions)])
                self.assert_fallback(output, "schema_error")

    def test_invalid_envelope(self):
        for raw in (b"not json", b"{}", b'{"choices": []}'):
            with self.subTest(raw=raw):
                output, _ = self.run_main([io.BytesIO(raw)])
                self.assertEqual(output["mode"], "rules")
                self.assertIn(output["fallback_reason"], ("parse_error", "schema_error"))

    def test_500_then_success_reuses_exact_request_bytes(self):
        output, urlopen = self.run_main([self.http_error(500), self.reply()])
        self.assertEqual(output["mode"], "model")
        self.assertNotIn("fallback_reason", output)
        self.assertEqual(urlopen.call_count, 2)
        first, second = urlopen.call_args_list
        self.assertIs(first.args[0], second.args[0])
        self.assertIs(first.args[0].data, second.args[0].data)
        self.assertEqual(first.kwargs, {"timeout": 60})
        self.assertEqual(second.kwargs, {"timeout": 60})

    def test_500_twice_falls_back(self):
        output, urlopen = self.run_main([
            self.http_error(500), self.http_error(500),
        ])
        self.assert_fallback(output, "http_error")
        self.assertEqual(urlopen.call_count, 2)

    def test_4xx_does_not_retry(self):
        for status in (400, 401, 403, 429):
            with self.subTest(status=status):
                output, urlopen = self.run_main([self.http_error(status)])
                self.assert_fallback(output, "http_error")
                self.assertEqual(urlopen.call_count, 1)

    def test_timeout_falls_back_after_one_retry(self):
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                errors = [TimeoutError(self.FAKE_KEY) for _ in range(2)]
                if wrapped:
                    errors = [urllib.error.URLError(error) for error in errors]
                output, urlopen = self.run_main(errors)
                self.assert_fallback(output, "timeout")
                self.assertEqual(urlopen.call_count, 2)

    def test_connection_error_retries(self):
        output, urlopen = self.run_main([
            urllib.error.URLError(ConnectionRefusedError("sample")),
            self.reply(),
        ])
        self.assertEqual(output["mode"], "model")
        self.assertEqual(urlopen.call_count, 2)

    def test_connection_error_twice_falls_back(self):
        output, urlopen = self.run_main([
            ConnectionResetError("sample"), ConnectionResetError("sample"),
        ])
        self.assert_fallback(output, "connection_error")
        self.assertEqual(urlopen.call_count, 2)

    def test_guard_overrides_forbidden_model_buy(self):
        decisions = [
            {"signal_id": r["signal_id"], "buy": True, "reason": "sample"}
            for r in self.rules
        ]
        output, _ = self.run_main([self.reply(decisions=decisions)])
        self.assertEqual(output["mode"], "model")
        by_id = {d["signal_id"]: d for d in output["decisions"]}
        self.assertFalse(by_id["sample-005"]["buy"])
        self.assertIn("guard overrode", by_id["sample-005"]["source"])
        self.assertTrue(by_id["sample-001"]["buy"])

    def test_model_without_key_falls_back(self):
        output, urlopen = self.run_main(key=False)
        self.assert_fallback(output, "missing_api_key")
        urlopen.assert_not_called()
        self.preflight.assert_not_awaited()

    def test_auto_without_key_uses_rules_without_fallback_reason(self):
        output, urlopen = self.run_main(mode="auto", key=False)
        self.assertEqual(output["mode"], "rules")
        self.assertNotIn("fallback_reason", output)
        urlopen.assert_not_called()

    def test_auto_with_key_uses_model(self):
        output, urlopen = self.run_main([self.reply()], mode="auto")
        self.assertEqual(output["mode"], "model")
        urlopen.assert_called_once()

    def test_explicit_rules_does_not_call_model(self):
        output, urlopen = self.run_main(mode="rules")
        self.assertEqual(output["mode"], "rules")
        self.assertNotIn("fallback_reason", output)
        urlopen.assert_not_called()
        self.preflight.assert_not_awaited()

    def test_required_attestation_fails_closed_before_completion(self):
        output, urlopen = self.run_main(required=True)
        self.assert_fallback(output, "attestation_error")
        urlopen.assert_not_called()
        self.save.assert_called_once()

    def test_fallback_output_passes_check(self):
        output, _ = self.run_main([self.http_error(500), self.http_error(500)])
        fixtures = {
            evaluate.OUT: output,
            evaluate.FEED: self.feed,
            evaluate.POLICY: POLICY,
        }
        captured = io.StringIO()
        with (
            patch.object(evaluate, "load_json", side_effect=fixtures.__getitem__),
            redirect_stdout(captured),
        ):
            evaluate.check()
        self.assertIn("CHECK OK:", captured.getvalue())

    def test_required_provider_signature_succeeds(self):
        output, _ = self.run_main(
            [self.reply()], required=True, preflight_ok=True,
            verification=self.result(),
        )
        self.assertEqual(output["mode"], "model")
        self.assertTrue(self.saved_evidence.audit["require_attestation"])

    def test_required_gateway_signature_falls_back(self):
        output, _ = self.run_main(
            [self.reply()], required=True, preflight_ok=True,
            verification=self.result("gateway"),
        )
        self.assert_fallback(output, "attestation_error")
        self.assertEqual(
            self.save.call_args.kwargs["response"]["overall_verdict"],
            "verified gateway-only",
        )

    def test_optional_gateway_signature_keeps_model(self):
        output, _ = self.run_main(
            [self.reply()], preflight_ok=True,
            verification=self.result("gateway"),
        )
        self.assertEqual(output["mode"], "model")

    def test_required_missing_signature_falls_back(self):
        output, _ = self.run_main(
            [self.reply()], required=True, preflight_ok=True,
        )
        self.assert_fallback(output, "attestation_error")

    def test_completion_id_locations(self):
        for envelope in (
            {"id": "sample"},
            {"choices": [{"id": "sample"}]},
            {"choices": [{"message": {"id": "sample"}}]},
        ):
            self.assertEqual(
                evaluate.completion_identifier(json.dumps(envelope).encode()),
                "sample",
            )

    def test_optional_attestation_exceptions_keep_model_and_save(self):
        for failing in ("preflight", "signature", "verify"):
            with self.subTest(failing=failing):
                evidence = self.evidence(True)
                preflight = AsyncMock(
                    side_effect=ValueError(self.FAKE_KEY)
                    if failing == "preflight" else None,
                    return_value=evidence,
                )
                with (
                    patch.object(attest, "preflight", new=preflight),
                    patch.object(
                        attest, "get_signature",
                        side_effect=ValueError(self.FAKE_KEY)
                        if failing == "signature" else None,
                        return_value={},
                    ),
                    patch.object(
                        attest, "verify_response",
                        side_effect=ValueError(self.FAKE_KEY)
                        if failing == "verify" else None,
                        return_value=evaluate.unverified_result(b"sample"),
                    ),
                    patch.object(attest, "save") as save,
                    patch.object(evaluate, "http_bytes", return_value=self.reply().getvalue()),
                ):
                    decisions = evaluate.ask_model(
                        self.feed, POLICY, "SAMPLE DATA", self.FAKE_KEY,
                    )
                self.assertEqual(decisions, self.rules)
                save.assert_called_once()

    def test_preflight_precedes_completion_and_algorithm_is_shared(self):
        events = []
        evidence = attest.Preflight(evaluate.MODEL, "ed25519", "00" * 32)
        evidence.finished = True

        async def preflight(model, algo):
            events.append(("preflight", model, algo))
            return evidence

        def completion(request):
            events.append(("completion",))
            return self.reply().getvalue()

        def signature(completion_id, algo):
            events.append(("signature", completion_id, algo))
            return {"error_code": "sample"}

        with (
            patch.dict(os.environ, {"NEAR_AI_SIGNING_ALGO": "ed25519"}),
            patch.object(attest, "preflight", side_effect=preflight),
            patch.object(evaluate, "http_bytes", side_effect=completion),
            patch.object(attest, "get_signature", side_effect=signature),
            patch.object(attest, "save"),
        ):
            evaluate.ask_model(self.feed, POLICY, "SAMPLE DATA", self.FAKE_KEY)
        self.assertEqual(events, [
            ("preflight", evaluate.MODEL, "ed25519"),
            ("completion",),
            ("signature", "sample-completion", "ed25519"),
        ])

    def test_secret_leak_with_real_audit_writes_and_mocked_http(self):
        # Exercise real preflight, signature fetching, verification and save.
        # Empty attestation reports are intentionally not verified. Optional
        # attestation still permits the successful model path.
        real_save = attest.save
        for scenario in ("success", "http_error", "parse_error"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                notes = root / "notes"
                output_dir = root / "stages/02_evaluate/output"
                audit_path = notes / "near-ai-attestation.json"
                output_path = output_dir / "decisions.json"
                rules_path = root / "rules.md"
                rules_path.write_text("SAMPLE DATA rules", encoding="utf-8")
                calls = []
                stdout = io.StringIO()
                stderr = io.StringIO()
                sensitive = "Bearer " + self.FAKE_KEY

                def http(request, *args, **kwargs):
                    url = request.full_url if hasattr(request, "full_url") else request
                    if "/attestation/report?" in url:
                        calls.append("report")
                        return io.BytesIO(json.dumps({
                            "model_attestations": [],
                            "gateway_attestation": None,
                            "sample_note": sensitive,
                        }).encode())
                    if url.endswith("/chat/completions"):
                        calls.append("completion")
                        if scenario == "http_error":
                            raise self.http_error(500)
                        if scenario == "parse_error":
                            return self.reply(content="not json " + sensitive)
                        decisions = [{**r, "reason": sensitive} for r in self.rules]
                        return self.reply(decisions=decisions)
                    if "/signature/" in url:
                        calls.append("signature")
                        return io.BytesIO(json.dumps({
                            "error_code": "sample_unavailable",
                            "message": sensitive,
                        }).encode())
                    raise AssertionError("unexpected HTTP endpoint")

                def write_output(path, value):
                    target = Path(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps(value), encoding="utf-8")

                def save(evidence, response=None, completion_id=None):
                    return real_save(
                        evidence, response=response,
                        completion_id=completion_id, output=audit_path,
                    )

                fixtures = {evaluate.FEED: self.feed, evaluate.POLICY: POLICY}
                with (
                    patch.dict(os.environ, {"NEAR_AI_CLOUD_API_KEY": self.FAKE_KEY}, clear=True),
                    patch.object(sys, "argv", ["evaluate.py", "--mode", "model"]),
                    patch.object(evaluate, "OUT", str(output_path)),
                    patch.object(evaluate, "RULES_DOC", str(rules_path)),
                    patch.object(evaluate, "load_json", side_effect=fixtures.__getitem__),
                    patch.object(evaluate, "write_json", side_effect=write_output),
                    patch.object(attest, "save", side_effect=save),
                    patch.object(urllib.request, "urlopen", side_effect=http),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    evaluate.main()

                self.assertTrue(output_path.is_file())
                self.assertTrue(audit_path.is_file())
                files = [
                    path
                    for directory in (notes, output_dir)
                    for path in directory.rglob("*")
                    if path.is_file()
                ]
                # Raw report persistence must also be covered.
                self.assertTrue(any(
                    path.parent.name == "near-ai-attestation-reports"
                    for path in files
                ))
                for path in files:
                    raw = path.read_bytes()
                    self.assertNotIn(self.FAKE_KEY.encode(), raw, str(path))
                    self.assertNotIn(b"Bearer", raw, str(path))
                for captured in (stdout.getvalue(), stderr.getvalue()):
                    self.assertNotIn(self.FAKE_KEY, captured)
                    self.assertNotIn("Bearer", captured)
                output = json.loads(output_path.read_text(encoding="utf-8"))
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
                self.assertEqual(audit["overall_verdict"], "not verified")
                self.assertEqual(calls[0], "report")
                if scenario == "success":
                    self.assertEqual(output["mode"], "model")
                    self.assertEqual(calls, ["report", "completion", "signature"])
                else:
                    self.assert_fallback(output, scenario)
                    self.assertEqual(
                        calls,
                        ["report", "completion", "completion"]
                        if scenario == "http_error"
                        else ["report", "completion", "signature"],
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ReviewFixTests(unittest.TestCase):
    """Key redaction and attestation override checks, Nov 12 2026."""

    def test_raw_report_keeps_upstream_words_but_drops_key(self):
        key = "sk-FAKE-LEAKCHECK-0000"
        raw = {"app_compose": "proxy_set_header Authorization; bearer realm", "x": "Bearer " + key}
        out = evaluate.redact_key_only(raw, key)
        self.assertEqual(out["app_compose"], raw["app_compose"])
        self.assertNotIn(key, json.dumps(out))
        self.assertEqual(out["x"], "[redacted]")

    def test_required_attestation_refuses_endpoint_override(self):
        with patch.object(evaluate, "BASE_URL", "https://example.invalid/v1"), \
                patch.object(urllib.request, "urlopen", side_effect=AssertionError("no HTTP")), \
                patch.object(evaluate.attest, "preflight", side_effect=AssertionError("no preflight")), \
                patch.object(evaluate, "save_audit", return_value=None):
            with self.assertRaises(evaluate.AttestationError):
                evaluate.ask_model({"signals": []}, {}, "SAMPLE DATA", "sk-FAKE-LEAKCHECK-0000",
                                   require_attestation=True)


class HttpErrorLabelTests(unittest.TestCase):
    def make(self, code, body):
        return urllib.error.HTTPError(
            "https://example.invalid", code, "sample", {}, io.BytesIO(body),
        )

    def test_only_plain_error_type_kept(self):
        key = "sk-FAKE-LEAKCHECK-0000"
        body = json.dumps({"error": {"type": "insufficient_credits", "message": "Bearer " + key}}).encode()
        self.assertEqual(evaluate.http_error_type(self.make(402, body)), "insufficient_credits")
        odd = json.dumps({"error": {"type": "Bearer " + key}}).encode()
        self.assertIsNone(evaluate.http_error_type(self.make(400, odd)))
        self.assertIsNone(evaluate.http_error_type(self.make(400, b"not json")))

    def test_http_bytes_attaches_label_without_retry_on_4xx(self):
        error = self.make(400, b'{"error": {"type": "invalid_request_error"}}')
        with patch.object(urllib.request, "urlopen", side_effect=error) as opened:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                evaluate.http_bytes("https://example.invalid")
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(caught.exception.error_type, "invalid_request_error")
