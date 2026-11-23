"""Regex rules for known secret formats + the generic suspicious-assignment rule."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    secret_type: str
    regex: re.Pattern
    confidence: float
    group: int = 1          # capture group holding the secret value
    kind: str = "token"     # token | db_url | pem


def _r(p: str, flags: int = 0) -> re.Pattern:
    return re.compile(p, flags)


# Order matters: earlier rules claim their span first (anthropic before openai).
RULES: list[Rule] = [
    Rule("pem", "private_key", _r(r"(-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----)"), 0.95, kind="pem"),
    Rule("aws", "aws_access_key_id", _r(r"(?<![A-Z0-9])((?:AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16})(?![A-Z0-9])"), 0.9),
    Rule("gh_fine", "github_token", _r(r"\b(github_pat_[A-Za-z0-9_]{60,255})\b"), 0.95),
    Rule("gh", "github_token", _r(r"\b(gh[pousr]_[A-Za-z0-9]{36,255})\b"), 0.95),
    Rule("anthropic", "anthropic_api_key", _r(r"(?<![A-Za-z0-9_-])(sk-ant-[A-Za-z0-9_-]{20,})"), 0.95),
    Rule("openai", "openai_api_key",
         _r(r"(?<![A-Za-z0-9_-])(sk-(?!ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,})"), 0.9),
    Rule("stripe", "stripe_secret_key", _r(r"\b(sk_live_[A-Za-z0-9]{20,})\b"), 0.95),
    Rule("stripe_rk", "stripe_restricted_key", _r(r"\b(rk_live_[A-Za-z0-9]{20,})\b"), 0.95),
    Rule("slack", "slack_token", _r(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"), 0.9),
    Rule("google", "google_api_key", _r(r"\b(AIza[0-9A-Za-z_-]{35})(?![0-9A-Za-z_-])"), 0.9),
    Rule("db_url", "database_url",
         _r(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?)://"
            r"([^:\s/@\"']+):([^@\s\"'/]+)@[^\s\"'/:]+"), 0.85, group=2, kind="db_url"),
]

SUSPICIOUS_NAME = r"(?:password|passwd|pwd|secret|token|api_?key|auth|credential)"
GENERIC = re.compile(
    r"(?P<name>[A-Za-z0-9_.$-]*" + SUSPICIOUS_NAME + r"[A-Za-z0-9_.-]*)"
    r"[\"']?\s*(?::=|=>|=|:)\s*"
    r"(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)'|(?P<bare>[^\s,;#\"']+))",
    re.IGNORECASE,
)
GENERIC_CONFIDENCE = 0.6


@dataclass(frozen=True)
class Hit:
    rule: Rule | None
    secret_type: str
    value: str
    span: tuple[int, int]          # span of the secret value in the line
    confidence: float
    name: str = ""                 # assigned-to identifier (generic rule)
    quoted: bool = True

    def __repr__(self) -> str:      # never print the value
        return f"Hit({self.secret_type}, span={self.span})"


def match_known(line: str) -> list[Hit]:
    hits: list[Hit] = []
    claimed: list[tuple[int, int]] = []
    for rule in RULES:
        for m in rule.regex.finditer(line):
            whole = m.span(0)
            if any(whole[0] < e and s < whole[1] for s, e in claimed):
                continue
            claimed.append(whole)
            hits.append(Hit(rule, rule.secret_type, m.group(rule.group), m.span(rule.group), rule.confidence))
    return hits


def match_generic(line: str) -> list[Hit]:
    out = []
    for m in GENERIC.finditer(line):
        for g, quoted in (("dq", True), ("sq", True), ("bare", False)):
            if m.group(g) is not None:
                out.append(Hit(None, "generic_secret", m.group(g), m.span(g), GENERIC_CONFIDENCE,
                               name=m.group("name"), quoted=quoted))
                break
    return out
