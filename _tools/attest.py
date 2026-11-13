#!/usr/bin/env python3
"""SAMPLE DATA attestation checks. NEAR is Oralys's home chain.

Preflight evidence stays in memory for response verification. Saved output is
an audit record, not a substitute for the preflight used for a completion.
"""
import argparse
import asyncio
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import secrets
import struct
import time
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

# The only env var read for the NEAR AI Cloud key. NEAR_API_KEY is never read.
KEY_ENV = "NEAR_AI_CLOUD_API_KEY"
MODEL = "z-ai/glm-5.3-flash"
API = "https://cloud-api.near.ai/v1"
NRAS = "https://nras.attestation.nvidia.com/v3/attest/gpu"
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "notes/near-ai-attestation.json"
RAW_LIMIT = 512 * 1024
QUOTE_CHECKS = (
    "tcb_status_UpToDate",
    "tdx_debug_disabled",
    "report_data_binds_signer",
    "report_data_binds_nonce",
    "http_report_data_equals_quote",
    "mrconfigid_matches_app_compose",
    "rtmr3_event_log_replay",
)


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def hex_bytes(value, length=None):
    if not isinstance(value, str):
        raise ValueError("expected hex text")
    result = bytes.fromhex(value.removeprefix("0x"))
    if length is not None and len(result) != length:
        raise ValueError("incorrect byte length")
    return result


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def record(checks, name, function):
    try:
        checks[name] = "pass" if function() else "fail: mismatch"
    except Exception as exc:
        checks[name] = "fail: invalid evidence ({})".format(type(exc).__name__)


def all_pass(checks):
    return bool(checks) and all(value == "pass" for value in checks.values())


def identity(address, algo):
    lengths = {"ecdsa": 20, "ed25519": 32}
    return hex_bytes(address, lengths[algo])


def replay_rtmr3(event_log):
    events = decoded(event_log)
    if not isinstance(events, list):
        raise ValueError("event log must be a list")
    current = bytes(48)
    for event in events:
        if event.get("imr") != 3:
            continue
        digest = hashlib.sha384(
            struct.pack("<I", event["event_type"])
            + b":" + event["event"].encode("utf-8")
            + b":" + hex_bytes(event.get("event_payload") or "")
        ).digest()
        if event.get("digest") and hex_bytes(event["digest"], 48) != digest:
            raise ValueError("event digest mismatch")
        current = hashlib.sha384(current + digest).digest()
    return current


def binding_checks(report, fields, nonce, algo):
    """Pure checks, also used with saved verified quote fields in tests."""
    checks = {}
    record(checks, "signing_algo", lambda: report["signing_algo"] == algo)
    record(
        checks, "signing_identity_length",
        lambda: bool(identity(report["signing_address"], algo)),
    )
    record(
        checks, "request_nonce_echo",
        lambda: hex_bytes(report["request_nonce"], 32) == hex_bytes(nonce, 32),
    )
    if fields is None:
        for name in QUOTE_CHECKS:
            if name != "http_report_data_equals_quote" or "report_data" in report:
                checks[name] = "not verified: verified quote fields unavailable"
        return checks

    record(checks, "tcb_status_UpToDate",
           lambda: fields["tcb_status"] == "UpToDate")
    record(checks, "tdx_debug_disabled",
           lambda: hex_bytes(fields["td_attributes"], 8)[0] & 1 == 0)
    record(
        checks, "report_data_binds_signer",
        lambda: hex_bytes(fields["report_data"], 64)[:32]
        == identity(report["signing_address"], algo).ljust(32, b"\0"),
    )
    record(
        checks, "report_data_binds_nonce",
        lambda: hex_bytes(fields["report_data"], 64)[32:] == hex_bytes(nonce, 32),
    )
    if "report_data" in report:
        record(
            checks, "http_report_data_equals_quote",
            lambda: hex_bytes(report["report_data"], 64)
            == hex_bytes(fields["report_data"], 64),
        )
    record(
        checks, "mrconfigid_matches_app_compose",
        lambda: hex_bytes(fields["mr_config_id"], 48)
        == b"\x01"
        + hashlib.sha256(
            decoded(report["info"]["tcb_info"])["app_compose"].encode("utf-8")
        ).digest()
        + bytes(15),
    )
    record(
        checks, "rtmr3_event_log_replay",
        lambda: replay_rtmr3(report["event_log"])
        == hex_bytes(fields["rt_mr3"], 48),
    )
    return checks


def http_json(url, *, data=None, headers=None):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(request, timeout=90) as response:
        # Bound remote input independently of the commit size limit.
        body = response.read(8 * 1024 * 1024 + 1)
    if len(body) > 8 * 1024 * 1024:
        raise ValueError("response exceeds size limit")
    return json.loads(body)


def gpu_checks(report, nonce, http=http_json):
    checks = {}
    try:
        payload = decoded(report["nvidia_payload"])
        if not isinstance(payload, dict):
            raise ValueError("GPU payload must be an object")
        record(
            checks, "gpu_nonce",
            lambda: hex_bytes(payload["nonce"], 32) == hex_bytes(nonce, 32),
        )
    except Exception:
        return {"gpu_evidence": "fail: missing or malformed GPU evidence"}
    if checks["gpu_nonce"] != "pass":
        checks["gpu_nras_overall_result"] = "not verified: GPU nonce failed"
        return checks
    try:
        answer = http(
            NRAS,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if not isinstance(answer, list) or not answer:
            raise ValueError("empty NRAS result")
        claims = []
        for entry in answer:
            # NRAS may append a metadata object after the JWT entries.
            if not (isinstance(entry, list) and len(entry) == 2 and entry[0] == "JWT"):
                continue
            parts = entry[1].split(".")
            if len(parts) != 3:
                raise ValueError("malformed token")
            encoded = parts[1] + "=" * (-len(parts[1]) % 4)
            claims.append(json.loads(base64.urlsafe_b64decode(encoded)))
        if not claims:
            raise ValueError("unexpected NRAS result")
        checks["gpu_nras_overall_result"] = (
            "pass"
            if all(c.get("x-nvidia-overall-att-result") is True for c in claims)
            else "fail: NRAS did not report success"
        )
    except Exception as exc:
        checks["gpu_nras_overall_result"] = (
            "not verified: NRAS request or result failed ({})".format(type(exc).__name__)
        )
    return checks


async def verify_report(label, report, nonce, algo, model, http=http_json):
    if not isinstance(report, dict):
        report = {}
    result = {
        "label": label,
        "signing_algo": report.get("signing_algo"),
        "signing_address": report.get("signing_address"),
        "model": report.get("model_name"),
        "tcb_status": None,
        "checks": {},
    }
    checks = result["checks"]
    fields = None
    try:
        qvl = importlib.import_module("dcap_qvl")
    except ImportError:
        checks["dcap_quote_signature_and_collateral"] = (
            "not verified: dcap-qvl not installed"
        )
    else:
        try:
            verified = await qvl.get_collateral_and_verify(
                hex_bytes(report["intel_quote"])
            )
            fields = json.loads(verified.to_json())["report"]["TD10"]
            if not isinstance(fields, dict):
                raise ValueError("missing TD10 fields")
            fields = {**fields, "tcb_status": verified.status}
            result["tcb_status"] = verified.status
            checks["dcap_quote_signature_and_collateral"] = "pass"
        except Exception as exc:
            fields = None
            checks["dcap_quote_signature_and_collateral"] = (
                "fail: quote verification failed ({})".format(type(exc).__name__)
            )
    checks.update(binding_checks(report, fields, nonce, algo))
    if label != "gateway":
        record(checks, "model_name", lambda: report["model_name"] == model)
        checks.update(gpu_checks(report, nonce, http))
    result["verified"] = all_pass(checks)
    return result


class Preflight:
    """Live evidence handle. Do not reconstruct this from a saved audit file."""

    def __init__(self, model, algo, nonce):
        self.model = model
        self.signing_algo = algo
        self.nonce = nonce
        self.reports = []
        self.raw = None
        self.finished = False
        self.audit = {
            "data_label": "SAMPLE DATA",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "signing_algo": algo,
            "nonce": nonce,
            "checks": {},
            "reports": self.reports,
            "completion_id": None,
            "request_sha256": None,
            "response_sha256": None,
            "signature_kind": None,
            "overall_verdict": "not verified",
            "scope": "preflight only",
            "limitations": [
                "No TLS binding.",
                "No measurement allowlist.",
                "NVIDIA tokens are not locally signature-verified.",
                "Preflight alone does not verify a completion.",
            ],
        }


async def preflight(model=MODEL, signing_algo="ecdsa", *, http=http_json):
    if signing_algo not in ("ecdsa", "ed25519"):
        raise ValueError("unsupported signing algorithm")
    evidence = Preflight(model, signing_algo, secrets.token_hex(32))
    checks = evidence.audit["checks"]
    query = urllib.parse.urlencode({
        "model": model,
        "provider": "near",
        "include_tls_fingerprint": "false",
        "signing_algo": signing_algo,
        "nonce": evidence.nonce,
    })
    try:
        body = http(
            API + "/attestation/report?" + query,
            headers={"Accept": "application/json", "x-no-aliasing": "true"},
        )
        if not isinstance(body, dict):
            raise ValueError("report must be an object")
        evidence.raw = body
        checks["report_fetch"] = "pass"
    except Exception as exc:
        checks["report_fetch"] = (
            "not verified: report request failed ({})".format(type(exc).__name__)
        )
        evidence.finished = True
        return evidence

    candidates = body.get("model_attestations")
    valid_candidates = isinstance(candidates, list) and bool(candidates)
    checks["model_candidates_present"] = (
        "pass" if valid_candidates else "fail: no model candidates"
    )
    evidence.reports.append(await verify_report(
        "gateway", body.get("gateway_attestation"), evidence.nonce,
        signing_algo, model, http,
    ))
    if isinstance(candidates, list):
        for index, candidate in enumerate(candidates):
            evidence.reports.append(await verify_report(
                "model_{}".format(index), candidate, evidence.nonce,
                signing_algo, model, http,
            ))
    if all_pass(checks) and all(r["verified"] for r in evidence.reports):
        evidence.audit["overall_verdict"] = "verified"
    evidence.finished = True
    return evidence


def get_signature(completion_id, signing_algo, *, http=http_json,
                  attempts=3, delay=1.0, sleep=time.sleep):
    """Fetch a signature, retrying only bounded 404 responses.

    Call only after the completion, with its preflight algorithm.
    """
    if signing_algo not in ("ecdsa", "ed25519"):
        raise ValueError("unsupported signing algorithm")
    if not isinstance(completion_id, str) or not completion_id:
        raise ValueError("completion id is required")
    if not 1 <= attempts <= 10 or not 0 <= delay <= 10:
        raise ValueError("retry bounds exceeded")
    key = os.environ.get(KEY_ENV)
    if not key:
        return {"error_code": "missing_key", "message": "Signature unavailable"}
    url = (
        API + "/signature/" + urllib.parse.quote(completion_id, safe="")
        + "?" + urllib.parse.urlencode({"signing_algo": signing_algo})
    )
    for attempt in range(attempts):
        try:
            result = http(url, headers={
                "Accept": "application/json",
                "Authorization": "Bearer " + key,
            })
            if not isinstance(result, dict):
                raise ValueError("signature result must be an object")
            return result
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and attempt + 1 < attempts:
                sleep(delay)
                continue
            return {"error_code": str(exc.code), "message": "Signature unavailable"}
        except Exception:
            return {"error_code": "request_failed", "message": "Signature unavailable"}
    return {"error_code": "not_recorded", "message": "Signature unavailable"}


def verify_signature(text, signature, address, algo):
    try:
        public = identity(address, algo)
        if algo == "ed25519":
            module = importlib.import_module("nacl.signing")
            module.VerifyKey(public).verify(text.encode("utf-8"), hex_bytes(signature, 64))
        else:
            module = importlib.import_module("eth_account")
            messages = importlib.import_module("eth_account.messages")
            recovered = module.Account.recover_message(
                messages.encode_defunct(text=text),
                signature=hex_bytes(signature, 65),
            )
            if identity(recovered, algo) != public:
                return "fail: recovered signer mismatch"
        return "pass"
    except ImportError:
        package = "pynacl" if algo == "ed25519" else "eth-account"
        return "not verified: {} not installed".format(package)
    except Exception:
        return "fail: invalid signature"


def verify_response(sig_json, request_bytes, response_bytes, model, verified):
    """Verify exact wire bytes against the pre-completion live evidence.

    The caller must obtain preflight before sending the completion request.
    JSON reserialization is not a substitute for the original wire bytes.
    """
    result = {
        "completion_id": None,
        "request_sha256": sha256(request_bytes),
        "response_sha256": sha256(response_bytes),
        "signature_kind": None,
        "checks": {},
        "overall_verdict": "not verified",
        "scope": "none",
    }
    checks = result["checks"]
    if not isinstance(verified, Preflight) or not verified.finished:
        checks["preflight"] = "not verified: live preflight required"
        return result
    if verified.model != model or verified.audit["overall_verdict"] != "verified":
        checks["preflight"] = "not verified: preflight model or checks failed"
        return result
    checks["preflight"] = "pass"
    if not isinstance(sig_json, dict) or "error_code" in sig_json:
        checks["signature_available"] = "not verified: signature unavailable"
        return result
    checks["signature_available"] = "pass"
    kind = sig_json.get("signature_kind")
    result["signature_kind"] = kind
    if kind not in ("provider_tee", "gateway"):
        checks["signature_kind"] = "not verified: absent or unknown signature kind"
        return result
    checks["signature_kind"] = "pass"
    algo = sig_json.get("signing_algo")
    record(checks, "signature_algo", lambda: algo == verified.signing_algo)
    expected = "{}:{}".format(result["request_sha256"], result["response_sha256"])
    if kind == "provider_tee":
        expected = model + ":" + expected
    record(checks, "signed_text", lambda: sig_json["text"] == expected)

    def matches():
        signer = identity(sig_json["signing_address"], algo)
        selected = []
        for report in verified.reports:
            eligible = (
                report["label"] == "gateway" if kind == "gateway"
                else report["label"] != "gateway" and report["model"] == model
            )
            if (
                eligible and report["verified"]
                and report["signing_algo"] == algo
                and identity(report["signing_address"], algo) == signer
            ):
                selected.append(report)
        return len(selected) == 1

    record(checks, "exactly_one_preflight_signer", matches)
    if not all_pass(checks):
        checks["signature_crypto"] = "not verified: signature binding checks failed"
        return result
    checks["signature_crypto"] = verify_signature(
        sig_json["text"], sig_json.get("signature"),
        sig_json["signing_address"], algo,
    )
    if all_pass(checks):
        result["scope"] = "provider_tee" if kind == "provider_tee" else "gateway-only"
        result["overall_verdict"] = (
            "verified" if kind == "provider_tee" else "verified gateway-only"
        )
    return result


def save(evidence, response=None, completion_id=None, output=OUTPUT):
    """Save audit metadata. A response result can be attached by turn c."""
    audit = dict(evidence.audit)
    if response is not None:
        audit.update(response)
        audit["checks"] = {**evidence.audit["checks"], **response["checks"]}
        audit["completion_id"] = completion_id
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if evidence.raw is not None:
        raw = json.dumps(evidence.raw, sort_keys=True, separators=(",", ":")).encode()
        audit["raw_reports"] = {"sha256": sha256(raw), "bytes": len(raw)}
        if len(raw) <= RAW_LIMIT:
            directory = output.parent / "near-ai-attestation-reports"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (sha256(raw) + ".json")
            path.write_bytes(raw)
            audit["raw_reports"]["path"] = str(path.relative_to(output.parent))
    output.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    return audit


def audit_checks(audit):
    for name, value in audit["checks"].items():
        yield name, value
    for report in audit["reports"]:
        for name, value in report["checks"].items():
            yield report["label"] + "/" + name, value


def read_audit(path):
    audit = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "timestamp", "model", "signing_algo", "nonce", "reports", "checks",
        "completion_id", "request_sha256", "response_sha256", "signature_kind",
        "overall_verdict",
    }
    if not isinstance(audit, dict) or not required <= audit.keys():
        raise ValueError("missing audit fields")
    datetime.fromisoformat(audit["timestamp"])
    hex_bytes(audit["nonce"], 32)
    if audit["signing_algo"] not in ("ecdsa", "ed25519"):
        raise ValueError("unsupported algorithm")
    if not isinstance(audit["model"], str) or not audit["model"]:
        raise ValueError("missing model")
    if not isinstance(audit["reports"], list) or not isinstance(audit["checks"], dict):
        raise ValueError("invalid audit checks")
    if audit["overall_verdict"] not in (
        "verified", "verified gateway-only", "not verified",
    ):
        raise ValueError("invalid verdict")
    for report in audit["reports"]:
        if not isinstance(report, dict) or not isinstance(report.get("checks"), dict):
            raise ValueError("invalid report")
        if not isinstance(report.get("label"), str):
            raise ValueError("invalid report label")
    values = list(audit_checks(audit))
    if not values:
        raise ValueError("missing checks")
    for name, value in values:
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("invalid check")
        if value != "pass" and not value.startswith(("fail: ", "not verified: ")):
            raise ValueError("invalid check status")
    if audit["overall_verdict"].startswith("verified"):
        if not audit["reports"] or any(value != "pass" for _, value in values):
            raise ValueError("verdict contradicts checks")
    return audit


def print_summary(audit):
    items = list(audit_checks(audit))
    print("SAMPLE DATA")
    print("Verified")
    for name, value in items:
        if value == "pass":
            print("  " + name)
    print("Not verified")
    for name, value in items:
        if value != "pass":
            print("  {}: {}".format(name, value))
    for limitation in audit.get("limitations", []):
        print("  " + limitation)
    print("Overall: " + audit["overall_verdict"])
    print("Scope: " + audit.get("scope", "unspecified"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--require-attestation", action="store_true")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--signing-algo", choices=("ecdsa", "ed25519"), default="ecdsa")
    args = parser.parse_args(argv)
    try:
        if args.check:
            audit = read_audit(OUTPUT)
        else:
            audit = save(asyncio.run(preflight(args.model, args.signing_algo)))
        print_summary(audit)
    except Exception as exc:
        print("Not verified: audit unavailable or malformed ({})".format(type(exc).__name__))
        return 1
    return int(args.require_attestation and audit["overall_verdict"] != "verified")


if __name__ == "__main__":
    raise SystemExit(main())
