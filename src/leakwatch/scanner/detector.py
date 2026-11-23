"""Detection pipeline: known-format regex → generic entropy rule → placeholder filters."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

from .diff import DiffLine, parse_patch, parse_unified, should_skip
from .entropy import shannon
from .filters import generic_value_reason, path_penalty, placeholder_reason
from .patterns import match_generic, match_known
from .redact import mask, scrub

log = logging.getLogger("leakwatch.scanner")
GENERIC_MIN_LEN = 8          # value must be LONGER than this
GENERIC_MIN_ENTROPY = 3.5


@dataclass
class Finding:
    secret_type: str
    rule_id: str
    file: str
    line: int
    masked: str
    confidence: float
    context: list[str]
    rules_note: str
    _secret: str = field(repr=False, compare=False, default="")

    def fingerprint(self, repo: str) -> str:
        return hashlib.sha256(f"{repo}\0{self.file}\0{self._secret}".encode()).hexdigest()

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def __repr__(self) -> str:
        return (f"Finding({self.secret_type} {self.file}:{self.line} {self.masked} "
                f"conf={self.confidence:.2f})")

    __str__ = __repr__


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    dropped: list[tuple[str, int, str, str]] = field(default_factory=list)  # file, line, type, reason
    skipped: list[tuple[str, str]] = field(default_factory=list)            # file, reason

    def extend(self, other: "ScanResult") -> None:
        self.findings += other.findings
        self.dropped += other.dropped
        self.skipped += other.skipped


def _context(lines: list[DiffLine], idx: int, secret: str, masked: str, pem: bool) -> list[str]:
    lo, hi = max(0, idx - 1), idx + (1 if pem else 2)
    out = []
    for dl in lines[lo:hi]:
        if abs(dl.line_no - lines[idx].line_no) > 1:
            continue
        text = dl.text.replace(secret, masked) if secret else dl.text
        out.append(scrub(text)[:200])
    return out


def scan_lines(path: str, lines: list[DiffLine]) -> ScanResult:
    res = ScanResult()
    seen: set[str] = set()
    penalty = path_penalty(path)
    for idx, dl in enumerate(lines):
        if not dl.added:
            continue
        known = match_known(dl.text)
        for h in known:
            kind = h.rule.kind
            if kind == "pem":
                nxt = lines[idx + 1].text if idx + 1 < len(lines) and lines[idx + 1].added else ""
                secret, masked = h.value + "\n" + nxt, h.value.replace("-----", "").strip() + " (key body hidden)"
                reason = None
            else:
                secret, masked = h.value, mask(h.value)
                reason = placeholder_reason(h.value, dl.text, strict=True)
            if reason:
                res.dropped.append((path, dl.line_no, h.secret_type, reason))
                continue
            if secret in seen:
                continue
            seen.add(secret)
            ctx_secret = "" if kind == "pem" else h.value
            res.findings.append(Finding(
                h.secret_type, h.rule.id, path, dl.line_no, masked, round(h.confidence * penalty, 3),
                _context(lines, idx, ctx_secret, masked, kind == "pem"),
                f"matched known format `{h.rule.id}`" + ("; test/docs path" if penalty < 1 else ""),
                _secret=secret))
        for h in match_generic(dl.text):
            if any(h.span[0] < k.span[1] and k.span[0] < h.span[1] for k in known):
                continue
            v = h.value
            reason = (("too-short" if len(v) <= GENERIC_MIN_LEN else None)
                      or generic_value_reason(v, h.quoted, path)
                      or placeholder_reason(v, dl.text)
                      or ("low-entropy" if shannon(v) < GENERIC_MIN_ENTROPY else None))
            if reason:
                res.dropped.append((path, dl.line_no, "generic_secret", reason))
                continue
            if v in seen:
                continue
            seen.add(v)
            m = mask(v)
            res.findings.append(Finding(
                "generic_secret", "generic", path, dl.line_no, m, round(h.confidence * penalty, 3),
                _context(lines, idx, v, m, False),
                f"high-entropy ({shannon(v):.1f} bits/char) value assigned to `{h.name}`"
                + ("; test/docs path" if penalty < 1 else ""),
                _secret=v))
    for f in res.findings:
        log.debug("candidate %r", f)
    return res


def scan_patch(path: str, patch: str | None) -> ScanResult:
    reason = should_skip(path, patch)
    if reason:
        return ScanResult(skipped=[(path, reason)])
    return scan_lines(path, parse_patch(patch))


def scan_unified(diff: str) -> ScanResult:
    res = ScanResult()
    for path, lines in parse_unified(diff).items():
        reason = should_skip(path, "")
        res.extend(ScanResult(skipped=[(path, reason)]) if reason else scan_lines(path, lines))
    return res


def scan_text(path: str, text: str) -> ScanResult:
    """Scan a whole file as if every line were added (used by the self-scan)."""
    return scan_lines(path, [DiffLine(i, t, True) for i, t in enumerate(text.split("\n"), 1)])
