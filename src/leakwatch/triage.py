"""LLM triage. The model sees ONLY masked data + locally computed features — never the raw secret."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from .gateway import GatewayError
from .llm import LLMUnavailable, OpenRouter
from .scanner.detector import Finding
from .scanner.entropy import shannon
from .scanner.filters import path_penalty
from .scanner.redact import scrub

log = logging.getLogger("leakwatch.triage")
VERDICTS = {"real", "placeholder", "unsure"}

SYSTEM = """You triage possible leaked secrets found in a git commit.
You only ever see a MASKED value (first 4 chars + "…" + last 2) plus locally computed features.
Decide if it is a REAL credential, an obvious PLACEHOLDER/test value, or UNSURE.
Random-looking values in a valid vendor format in non-test code are usually real.
Words like "your", "example", "changeme", "here", "dummy" or template syntax mean placeholder.
Reply with ONLY a JSON object, no prose, no code fences:
{"verdict": "real|placeholder|unsure", "confidence": 0.0-1.0, "why": "<one or two plain sentences>",
 "rotation_steps": ["<short imperative step>", "..."]}
rotation_steps: 3-5 concrete steps to revoke/rotate this kind of credential. Never invent URLs."""


@dataclass
class Triage:
    verdict: str
    confidence: float
    why: str
    rotation_steps: list[str] = field(default_factory=list)
    source: str = "rules"   # "llm:<model>" or "rules"


class TriageParseError(ValueError):
    pass


def features(f: Finding) -> dict:
    v = f._secret
    return {
        "secret_type": f.secret_type,
        "detector": f.rules_note,
        "file": f.file,
        "is_test_or_docs_path": path_penalty(f.file) < 1.0,
        "length": len(v),
        "entropy_bits_per_char": round(shannon(v), 2),
        "has_digits_and_letters": bool(re.search(r"\d", v) and re.search(r"[A-Za-z]", v)),
        "placeholder_markers_found": "none (rule filters passed)",
    }


def build_messages(f: Finding) -> list[dict]:
    payload = {"masked_value": f.masked, "features": features(f),
               "masked_context": [scrub(c) for c in f.context]}
    user = json.dumps(payload, ensure_ascii=False, indent=1)
    assert f._secret not in user, "raw secret must never reach the LLM"  # defense in depth
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse(text: str) -> Triage:
    """Extract and strictly validate the JSON object."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start < 0:
        raise TriageParseError("no JSON object")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise TriageParseError(f"invalid JSON: {e.msg}") from e
    if not isinstance(obj, dict):
        raise TriageParseError("not an object")
    verdict = str(obj.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        raise TriageParseError(f"bad verdict {verdict!r}")
    conf = obj.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        raise TriageParseError(f"bad confidence {conf!r}")
    why = obj.get("why", "")
    if not isinstance(why, str) or not why.strip():
        raise TriageParseError("missing why")
    steps = obj.get("rotation_steps", [])
    if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
        raise TriageParseError("rotation_steps must be a list of strings")
    steps = [scrub(s.strip())[:300] for s in steps if s.strip()][:8]
    return Triage(verdict, float(conf), scrub(why.strip())[:600], steps)


def rules_only(f: Finding, reason: str = "LLM unavailable") -> Triage:
    return Triage("unsure", f.confidence, f"Rules-only triage ({reason}): {f.rules_note}.", [], "rules")


def triage(f: Finding, llm: OpenRouter | None) -> Triage:
    if llm is None:
        return rules_only(f, "LLM disabled")
    messages = build_messages(f)
    try:
        text, model = llm.complete(messages)
        try:
            t = parse(text)
        except TriageParseError as e:
            log.info("malformed triage JSON from %s (%s); retrying once", model, e)
            retry = messages + [{"role": "assistant", "content": text[:2000]},
                                {"role": "user", "content": "That was not valid. Reply with ONLY the JSON object."}]
            text, model = llm.complete(retry, models=[model] + [m for m in llm.free_models() if m != model])
            t = parse(text)
        t.source = f"llm:{model}"
        return t
    except (LLMUnavailable, TriageParseError, GatewayError, httpx.HTTPError) as e:
        log.warning("triage fallback to rules-only: %s", str(e)[:200])
        return rules_only(f, "LLM unavailable" if isinstance(e, LLMUnavailable) else "LLM output invalid")
