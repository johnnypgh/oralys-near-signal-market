#!/usr/bin/env python3
"""Stage 02: decide which SAMPLE DATA signals to buy.

NEAR is Oralys's home chain. The model receives metadata only.
The guard always reapplies the rules. Model errors fall back to rules.

Usage: python3 -I _tools/evaluate.py [--mode auto|rules|model]
       [--require-attestation] [--check]
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fail, load_json, near, rules_decisions, write_json  # noqa: E402
import attest  # noqa: E402

FEED = "stages/01_intake/output/feed.json"
POLICY = "_shared/policy.json"
RULES_DOC = "_shared/buying-policy.md"
OUT = "stages/02_evaluate/output/decisions.json"
BASE_URL = os.environ.get("NEAR_AI_BASE_URL", "https://cloud-api.near.ai/v1")
MODEL = os.environ.get("NEAR_AI_MODEL", "z-ai/glm-5.3-flash")


class SchemaError(ValueError):
    """The model reply does not match the required schema."""


class AttestationError(Exception):
    """Required attestation is unavailable or invalid."""


def http_error_type(exc):
    """Return the API's error.type label only if it is a short plain token.

    The message and the rest of the body are never kept.
    """
    try:
        body = json.loads(exc.read(65536).decode("utf-8"))
        value = body["error"]["type"]
    except Exception:
        return None
    if isinstance(value, str) and re.fullmatch(r"[a-z_]{1,64}", value):
        return value
    return None


def http_bytes(request):
    """Read raw bytes, with one retry for timeout, connection error or 5xx."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            retry = 500 <= exc.code < 600
            exc.error_type = http_error_type(exc)
            exc.close()
            if not retry or attempt == 1:
                raise
        except urllib.error.URLError as exc:
            if not isinstance(exc.reason, OSError) or attempt == 1:
                raise
        except (TimeoutError, ConnectionError):
            if attempt == 1:
                raise


def _reject_constant(value):
    raise ValueError("nonstandard JSON constant")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def strict_json(value):
    return json.loads(
        value,
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )


def safe_record(value, key):
    """Remove secrets and authentication text from persisted data.

    Apply only after verification. Wire bytes must never be changed.
    """
    if isinstance(value, str):
        if key:
            value = value.replace(key, "[redacted]")
        value = re.sub(
            r"(?i)\bbearer\b(?:[ \t]+[^\s\"',}]+)?",
            "[redacted]",
            value,
        )
        return re.sub(r"(?i)authorization", "[redacted]", value)
    if isinstance(value, list):
        return [safe_record(item, key) for item in value]
    if isinstance(value, dict):
        return {
            safe_record(name, key): safe_record(item, key)
            for name, item in value.items()
            if not (
                isinstance(name, str)
                and name.lower() in ("authorization", "proxy-authorization")
            )
        }
    return value


def parse_decisions(raw_response, feed):
    envelope = strict_json(raw_response)
    try:
        content = envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise SchemaError("missing response content") from None
    if not isinstance(content, str):
        raise SchemaError("response content must be a string")

    parsed = strict_json(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("decisions"), list):
        raise SchemaError("expected an object with a decisions list")

    known = {signal["signal_id"] for signal in feed["signals"]}
    seen = set()
    for decision in parsed["decisions"]:
        if not isinstance(decision, dict):
            raise SchemaError("decision must be an object")
        if (
            not isinstance(decision.get("signal_id"), str)
            or type(decision.get("buy")) is not bool
            or not isinstance(decision.get("reason"), str)
        ):
            raise SchemaError("invalid decision fields")
        signal_id = decision["signal_id"]
        if signal_id not in known or signal_id in seen:
            raise SchemaError("unknown or duplicate signal id")
        seen.add(signal_id)
    return parsed["decisions"]


def completion_identifier(raw_response):
    envelope = strict_json(raw_response)
    if not isinstance(envelope, dict):
        return None
    candidates = [envelope.get("id")]
    choices = envelope.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        candidates.append(choices[0].get("id"))
        message = choices[0].get("message")
        if isinstance(message, dict):
            candidates.append(message.get("id"))
    return next(
        (value for value in candidates if isinstance(value, str) and value),
        None,
    )


def unverified_result(body, raw_response=None):
    return {
        "completion_id": None,
        "request_sha256": hashlib.sha256(body).hexdigest(),
        "response_sha256": (
            hashlib.sha256(raw_response).hexdigest()
            if raw_response is not None else None
        ),
        "signature_kind": None,
        "checks": {"response": "not verified: completion verification unavailable"},
        "overall_verdict": "not verified",
        "scope": "none",
    }


def redact_key_only(value, key):
    """Remove only the key value (and a bearer prefix in front of it).

    Raw attestation reports are fetched without a key and contain upstream
    configuration text (for example proxy rules that mention authorization).
    Rewriting those words would change app_compose and break re-verification
    of the saved report, so raw reports get exact key redaction only.
    """
    if not key:
        return value
    if isinstance(value, str):
        for needle in ("Bearer " + key, "bearer " + key, key):
            value = value.replace(needle, "[redacted]")
        return value
    if isinstance(value, list):
        return [redact_key_only(item, key) for item in value]
    if isinstance(value, dict):
        return {
            redact_key_only(name, key): redact_key_only(item, key)
            for name, item in value.items()
        }
    return value


def save_audit(evidence, result, completion_id, key):
    # Verification has finished. Sanitize metadata fully. Raw reports get exact
    # key redaction only so the saved evidence still verifies byte for byte.
    evidence.audit = safe_record(evidence.audit, key)
    evidence.raw = redact_key_only(evidence.raw, key)
    return attest.save(
        evidence,
        response=safe_record(result, key),
        completion_id=safe_record(completion_id, key),
    )


def ask_model(feed, policy, rules_text, key, require_attestation=False):
    listing = [
        {
            k: s[k]
            for k in ("signal_id", "topic", "title", "quality_score", "price_near")
        }
        for s in feed["signals"]
    ]
    prompt = (
        "You are a buyer agent. All data is SAMPLE DATA. "
        "NEAR is Oralys's home chain. "
        "Apply these rules and policy to the listing. "
        'Reply with JSON only: {"decisions":[{"signal_id":"...",'
        '"buy":true|false,"reason":"one short sentence"}]}.\n\n'
        f"RULES:\n{rules_text}\n\nPOLICY:\n{json.dumps(policy)}\n\n"
        f"LISTING (SAMPLE DATA):\n{json.dumps(listing)}"
    )
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "x-no-aliasing": "true",
            "Accept-Encoding": "identity",
        },
    )
    signing_algo = os.environ.get("NEAR_AI_SIGNING_ALGO", "ecdsa")
    evidence = attest.Preflight(MODEL, signing_algo, os.urandom(32).hex())
    result = unverified_result(body)
    completion_id = None

    try:
        try:
            evidence = asyncio.run(attest.preflight(MODEL, signing_algo))
        except Exception:
            evidence.audit["checks"]["preflight"] = (
                "not verified: preflight unavailable"
            )
            evidence.finished = True

        evidence.audit["require_attestation"] = require_attestation
        if require_attestation and (
            BASE_URL.rstrip("/") != attest.API or MODEL != attest.MODEL
        ):
            # The key must only go to the attested endpoint and model.
            raise AttestationError("endpoint or model override not allowed")
        preflight_ok = (
            evidence.finished
            and evidence.model == MODEL
            and evidence.signing_algo == signing_algo
            and evidence.audit.get("overall_verdict") == "verified"
        )
        if require_attestation and not preflight_ok:
            raise AttestationError("required preflight not verified")

        raw_response = http_bytes(request)
        result = unverified_result(body, raw_response)
        try:
            completion_id = completion_identifier(raw_response)
        except (ValueError, UnicodeError):
            # Preserve the strict parser's error classification below.
            completion_id = None

        try:
            sig_json = attest.get_signature(completion_id, signing_algo)
        except Exception:
            sig_json = {"error_code": "signature_unavailable"}

        try:
            result = attest.verify_response(
                sig_json, body, raw_response, MODEL, evidence,
            )
        except Exception:
            result = unverified_result(body, raw_response)

        provider_verified = (
            result.get("overall_verdict") == "verified"
            and result.get("signature_kind") == "provider_tee"
            and result.get("scope") == "provider_tee"
        )
        if require_attestation and not provider_verified:
            raise AttestationError("required provider response not verified")

        return parse_decisions(raw_response, feed)
    finally:
        try:
            save_audit(evidence, result, completion_id, key)
        except Exception:
            # No exception text is exposed. Optional audit write failures do
            # not discard otherwise usable model output.
            if require_attestation:
                raise AttestationError("required audit could not be saved") from None


def guard(model_decisions, rules):
    """The model can explain, but never buy something the rules forbid or skip silently."""
    by_id = {d.get("signal_id"): d for d in model_decisions}
    out = []
    for r in rules:
        m = by_id.get(r["signal_id"])
        if m is None:
            out.append({**r, "source": "rules (model gave no answer)"})
        elif bool(m.get("buy")) and not r["buy"]:
            out.append({**r, "source": "rules (guard overrode a model buy)"})
        else:
            out.append({
                "signal_id": r["signal_id"],
                "buy": bool(m.get("buy")),
                "reason": str(m.get("reason", "")),
                "source": "model",
            })
    return out


def fallback_class(exc):
    """Return a fixed label, never exception text, request headers or keys."""
    if isinstance(exc, AttestationError):
        return "attestation_error"
    if isinstance(exc, urllib.error.HTTPError):
        return "http_error"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        return "timeout" if isinstance(exc.reason, TimeoutError) else "connection_error"
    if isinstance(exc, ConnectionError):
        return "connection_error"
    if isinstance(exc, SchemaError):
        return "schema_error"
    if isinstance(exc, (ValueError, UnicodeError)):
        return "parse_error"
    return "model_error"


def check():
    d = load_json(OUT)
    feed, policy = load_json(FEED), load_json(POLICY)
    rules = {r["signal_id"]: r for r in rules_decisions(feed, policy)}
    prices = {s["signal_id"]: near(s["price_near"]) for s in feed["signals"]}
    spend = near(0)
    for x in d["decisions"]:
        if x["buy"] and not rules[x["signal_id"]]["buy"]:
            fail(f"{x['signal_id']} is marked buy but the rules forbid it")
        if x["buy"]:
            spend += prices[x["signal_id"]]
    if spend > near(policy["budget_near"]):
        fail(f"planned spend {spend} is over the budget {policy['budget_near']}")
    ids = [x["signal_id"] for x in d["decisions"]]
    if set(rules) != set(ids) or len(ids) != len(set(ids)):
        fail("decisions do not cover every signal in the feed exactly once")
    print(f"CHECK OK: {OUT} mode={d['mode']} buys={sum(x['buy'] for x in d['decisions'])} planned spend={spend} NEAR (budget {policy['budget_near']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "rules", "model"], default="auto")
    ap.add_argument("--require-attestation", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()

    feed, policy = load_json(FEED), load_json(POLICY)
    rules = rules_decisions(feed, policy)
    key = os.environ.get(attest.KEY_ENV)
    mode = a.mode if a.mode != "auto" else ("model" if key else "rules")
    fallback_reason = None
    http_status = None
    http_error_label = None
    candidates = rules
    model = None

    if mode == "model":
        if not key:
            mode = "rules"
            fallback_reason = "missing_api_key"
        else:
            try:
                rules_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    RULES_DOC,
                )
                with open(rules_path, encoding="utf-8") as rules_file:
                    rules_text = rules_file.read()
                candidates = ask_model(
                    feed, policy, rules_text, key,
                    require_attestation=a.require_attestation,
                )
                model = {"base_url": BASE_URL, "model": MODEL}
            except Exception as exc:
                mode = "rules"
                candidates = rules
                fallback_reason = fallback_class(exc)
                if isinstance(exc, urllib.error.HTTPError):
                    http_status = int(exc.code)
                    http_error_label = getattr(exc, "error_type", None)

    decisions = guard(candidates, rules)
    if mode == "rules":
        for decision in decisions:
            decision["source"] = "rules"

    titles = {s["signal_id"]: s for s in feed["signals"]}
    for decision in decisions:
        signal = titles[decision["signal_id"]]
        decision.update({
            "title": signal["title"],
            "quality_score": signal["quality_score"],
            "price_near": signal["price_near"],
        })
    output = {
        "mode": mode,
        "model": model,
        "policy": policy,
        "decisions": decisions,
        "require_attestation": a.require_attestation,
    }
    if fallback_reason is not None:
        output["fallback_reason"] = fallback_reason
    if http_status is not None:
        output["http_status"] = http_status
    if http_error_label is not None:
        output["http_error_type"] = http_error_label
    write_json(OUT, safe_record(output, key))
    print(f"wrote {OUT} (mode {mode}, {sum(d['buy'] for d in decisions)} to buy)")


if __name__ == "__main__":
    main()
