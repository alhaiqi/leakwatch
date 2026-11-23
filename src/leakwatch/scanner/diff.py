"""Unified-diff parsing → new-side lines with line numbers in the new file."""
from __future__ import annotations

import re
from typing import NamedTuple

MAX_PATCH_BYTES = 1024 * 1024
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "pipfile.lock", "cargo.lock",
    "go.sum", "composer.lock", "gemfile.lock", "bun.lockb", "uv.lock", "packages.lock.json",
}
VENDORED = ("vendor/", "node_modules/", "third_party/", ".venv/", "site-packages/")
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz", ".tgz", ".jar", ".so",
    ".dylib", ".dll", ".exe", ".bin", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov", ".mp3",
    ".wasm", ".pyc", ".class", ".sqlite", ".db",
}


class DiffLine(NamedTuple):
    line_no: int  # line number in the NEW file
    text: str
    added: bool


def parse_patch(patch: str | None) -> list[DiffLine]:
    """Parse GitHub's `files[].patch` (hunks only) into new-side lines."""
    out: list[DiffLine] = []
    if not patch:
        return out
    new_no = None
    for raw in patch.split("\n"):
        m = HUNK.match(raw)
        if m:
            new_no = int(m.group(1))
            continue
        if new_no is None or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            out.append(DiffLine(new_no, raw[1:], True))
            new_no += 1
        elif raw.startswith(" "):
            out.append(DiffLine(new_no, raw[1:], False))
            new_no += 1
        elif raw.startswith("-"):
            continue
        elif raw == "":
            continue  # trailing newline / blank separator
    return out


def added_lines(lines: list[DiffLine]) -> list[DiffLine]:
    return [l for l in lines if l.added]


def parse_unified(diff: str) -> dict[str, list[DiffLine]]:
    """Parse a full multi-file `git diff` into {new_path: new-side lines}. Deleted files are omitted."""
    files: dict[str, list[str]] = {}
    current: str | None = None
    in_hunk = False
    for raw in diff.split("\n"):
        if raw.startswith("diff --git "):
            current, in_hunk = None, False
            continue
        if not in_hunk and raw.startswith("+++ "):
            path = raw[4:].strip()
            current = None if path == "/dev/null" else (path[2:] if path.startswith("b/") else path)
            if current is not None:
                files.setdefault(current, [])
            continue
        if HUNK.match(raw):
            in_hunk = True
        if current is not None and in_hunk:
            files[current].append(raw)
    return {p: parse_patch("\n".join(body)) for p, body in files.items()}


def should_skip(path: str, patch: str | None = "") -> str | None:
    """Return a skip reason, or None if the file should be scanned."""
    low = path.lower()
    name = low.rsplit("/", 1)[-1]
    if name in LOCKFILES:
        return "lockfile"
    if any(low.startswith(v) or f"/{v}" in low for v in VENDORED):
        return "vendored"
    dot = name.rfind(".")
    if dot > 0 and name[dot:] in BINARY_EXT:
        return "binary"
    if patch is None:
        return "binary"  # GitHub omits `patch` for binary / huge files
    if len(patch.encode("utf-8", "ignore")) > MAX_PATCH_BYTES:
        return "too_large"
    return None
