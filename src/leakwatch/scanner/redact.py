"""Masking. The full secret must never leave memory: everything printed goes through here."""
from __future__ import annotations

import re

from .entropy import shannon
from .filters import DOTTED_IDENT, PATHLIKE
from .patterns import match_generic, match_known

ELLIPSIS = "…"
HIGH_ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{20,}")
# Not secrets, and needed for debugging: GitHub delivery GUIDs and git refs.
BENIGN = re.compile(r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|refs/(?:heads|tags)/[\w./-]+)$")


WORD_SEGMENT = re.compile(r"^(?:[a-z]+|[A-Z][a-z]+|[A-Z]+|\d{1,4})$")


def _wordy_identifier(tok: str) -> bool:
    """snake_case / kebab / dotted identifiers made of plain words, e.g. MAX_CONNECTION_RETRIES."""
    segs = [s for s in re.split(r"[_.-]", tok) if s]
    return len(segs) >= 2 and all(WORD_SEGMENT.match(s) for s in segs)


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
            if DOTTED_IDENT.match(h.value) or PATHLIKE.search(h.value):
                continue
            if len(h.value) > 8 and shannon(h.value) >= 3.0 and not any(
                    h.span[0] < e and s < h.span[1] for s, e in spans):
                spans.append(h.span)
        for m in HIGH_ENTROPY_TOKEN.finditer(line):
            tok = m.group(0)
            if BENIGN.match(tok) or _wordy_identifier(tok) or shannon(tok) < 3.5:
                continue
            # digits+letters (≥20) or any long token (≥24): random keys are often letters-only.
            # Long camelCase identifiers get masked too — acceptable over-masking (DEBUG_LOG #8).
            if (re.search(r"\d", tok) and re.search(r"[A-Za-z]", tok)) or len(tok) >= 24:
                spans.append(m.span())
        out_lines.append(_replace_spans(line, spans) if spans else line)
    return "\n".join(out_lines)
