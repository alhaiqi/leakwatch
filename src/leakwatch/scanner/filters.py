"""Cheap rule-based filters for obvious non-secrets."""
from __future__ import annotations

import re

# Structural markers: templating, env lookups, angle-bracket placeholders, masks.
STRUCTURAL = [
    (re.compile(r"\$\{[^}]*\}|\$\([^)]*\)|^\$[A-Z_][A-Z0-9_]*$"), "env-substitution"),
    (re.compile(r"\{\{.*?\}\}|\{\{|\}\}|\{%|%\([a-z_]+\)s|\{[A-Za-z_][\w.()\[\]'\"]*\}"), "template"),
    (re.compile(r"<[^>]{1,60}>"), "angle-placeholder"),
    (re.compile(r"os\.environ|getenv|process\.env|ENV\[|System\.getenv|import\.meta\.env", re.I), "env-lookup"),
    (re.compile(r"x{4,}|\*{4,}|#{4,}|\.{4,}", re.I), "mask-chars"),
    (re.compile(r"^(.)\1{5,}$"), "repeated-char"),
]
STRICT_ENV = re.compile(r"os\.environ|getenv\(|process\.env|ENV\[|import\.meta\.env")
STRICT_YOUR = re.compile(r"your[-_](?:api[-_]|access[-_]|secret[-_])?(?:key|token|secret|password|pat)(?![A-Za-z0-9])")
STRICT_MASK_RUN = re.compile(r"x{8,}|\*{8,}|#{8,}|\.{8,}|0{12,}", re.I)
# Long words: safe to apply even to random-looking known-format tokens (chance hit ~1e-6).
LONG_WORDS = ["example", "dummy", "sample", "placeholder", "changeme", "change_me", "replace",
              "redacted", "insert", "fixme", "notreal", "your_", "your-", "yourkey"]
# Short words: only for generic assignments, where values are human-chosen.
SHORT_WORDS = ["your", "here", "todo", "null", "none", "undefined", "foobar", "lorem", "sample"]
WEAK_PASSWORDS = {"password", "passwd", "pass", "secret", "admin", "root", "postgres", "mysql", "test",
                  "changeme", "letmein", "qwerty", "user", "guest", "default", "123456", "12345678"}


def placeholder_reason(value: str, line: str = "", strict: bool = False) -> str | None:
    """Return why `value` looks like a placeholder, or None. `strict` = known-format token."""
    low = value.lower()
    for rx, why in STRUCTURAL:
        if strict and why in ("mask-chars", "env-lookup"):
            continue  # short x/*/# runs and "getenv" occur by chance in random tokens (DEBUG_LOG #10)
        if rx.search(value):
            return why
    if strict and STRICT_MASK_RUN.search(value):
        return "mask-chars"
    if strict and STRICT_ENV.search(value):
        return "env-lookup"
    if strict and STRICT_YOUR.search(value):
        return "placeholder-word:your"
    for w in LONG_WORDS:
        if strict and len(w.strip("_-")) < 7:
            continue  # 5–6 letter words (dummy, fixme) appear by chance in random keys
        if w in low:
            return f"placeholder-word:{w.strip('_-')}"
    if not strict:
        for w in SHORT_WORDS:
            if w in low:
                return f"placeholder-word:{w}"
    if low.rstrip("0123456789!") in WEAK_PASSWORDS:
        return "weak-default"
    return None


PENALTY_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|docs?|examples?|fixtures?|testdata|samples?)/"
    r"|(^|/)test_[^/]*$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$"
    r"|\.(example|sample|template|dist)(\.|$)|(^|/)[^/]*\.example[^/]*$|\.md$|\.rst$",
    re.I,
)


def path_penalty(path: str) -> float:
    """Multiplier for confidence: tests/docs/examples are lowered, never auto-dropped."""
    return 0.6 if PENALTY_PATH.search(path) else 1.0


CODE_EXT = {"py", "js", "ts", "tsx", "jsx", "mjs", "cjs", "go", "rb", "java", "kt", "scala", "cs",
            "php", "rs", "swift", "c", "cc", "cpp", "h", "hpp", "m", "dart", "lua", "ex", "exs", "vue"}
PATHLIKE = re.compile(r"^(~|\.{0,2}/|[A-Za-z]:\\)|^[\w.-]+/[\w./-]+\.\w{1,5}$|^https?://[^:@]+$")
CALL_OR_INDEX = re.compile(r"[()\[\]]")
DOTTED_IDENT = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")


def is_code_file(path: str) -> bool:
    return path.rsplit(".", 1)[-1].lower() in CODE_EXT if "." in path.rsplit("/", 1)[-1] else False


def generic_value_reason(value: str, quoted: bool, path: str) -> str | None:
    """Shape checks for the generic rule (before entropy)."""
    if not quoted and (is_code_file(path) or CALL_OR_INDEX.search(value)):
        return "code-expression"
    if PATHLIKE.search(value):
        return "path-or-url"
    if DOTTED_IDENT.match(value):
        return "dotted-identifier"
    if " " in value.strip():
        return "prose"
    return None
