"""Masking. The full secret must never leave memory: everything printed goes through here."""
from __future__ import annotations

import re

from .entropy import shannon
from .patterns import match_generic, match_known

ELLIPSIS = "…"
HIGH_ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{20,}")


def mask(value: str) -> str:
    """first 4 + … + last 2 (values ≥ 10 chars); shorter values reveal less."""
    if len(value) >= 10:
        return value[:4] + ELLIPSIS + value[-2:]
    if len(value) >= 6:
        return value[:2] + ELLIPSIS
    return ELLIPSIS


def _replace_spans(text: str, spans: list[tuple[int, int]]) -> str:
    merged: list[list[int]] = []
    for s, e in sorted(spans):
        if merged and s < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    for s, e in reversed(merged):
        text = text[:s] + mask(text[s:e]) + text[e:]
    return text


def scrub(text: str) -> str:
    """Mask anything secret-shaped in arbitrary text (log lines, LLM context)."""
    out_lines = []
    for line in text.split("\n"):
        spans = [h.span for h in match_known(line) if h.rule.kind != "pem"]
        for h in match_generic(line):
            if len(h.value) > 8 and shannon(h.value) >= 3.0 and not any(
                    h.span[0] < e and s < h.span[1] for s, e in spans):
                spans.append(h.span)
        for m in HIGH_ENTROPY_TOKEN.finditer(line):
            tok = m.group(0)
            if re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok) and shannon(tok) >= 3.5:
                spans.append(m.span())
        out_lines.append(_replace_spans(line, spans) if spans else line)
    return "\n".join(out_lines)
