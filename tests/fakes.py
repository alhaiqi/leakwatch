"""Runtime generators for FAKE secrets in the right *format*.

Nothing here is a real credential, and no secret-shaped literal is stored in this repo:
prefixes are assembled from pieces so the source file itself scans clean.
"""
from __future__ import annotations

import re
import secrets
import string

ALNUM = string.ascii_letters + string.digits
UPPER_B32 = string.ascii_uppercase + "234567"


def _rand(alphabet: str, n: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _p(*parts: str) -> str:  # join prefix fragments (keeps literals out of source)
    return "".join(parts)


def aws_key() -> str:
    return _p("AK", "IA") + _rand(UPPER_B32, 16)


def github_pat() -> str:
    return _p("gh", "p_") + _rand(ALNUM, 36)


def github_oauth() -> str:
    return _p("gh", "o_") + _rand(ALNUM, 36)


def github_server() -> str:
    return _p("gh", "s_") + _rand(ALNUM, 36)


def github_fine() -> str:
    return _p("github", "_pat_") + _rand(ALNUM, 22) + "_" + _rand(ALNUM, 59)


def openai_key() -> str:
    return _p("s", "k-") + _rand(ALNUM, 48)


def openai_proj() -> str:
    return _p("s", "k-", "proj-") + _rand(ALNUM + "_-", 64)


def anthropic_key() -> str:
    return _p("s", "k-", "ant-", "api03-") + _rand(ALNUM + "_-", 93) + "AA"


def stripe_live() -> str:
    return _p("sk", "_live_") + _rand(ALNUM, 24)


def stripe_restricted() -> str:
    return _p("rk", "_live_") + _rand(ALNUM, 24)


def slack_token() -> str:
    return _p("xo", "xb-") + _rand(string.digits, 12) + "-" + _rand(string.digits, 13) + "-" + _rand(ALNUM, 24)


def google_key() -> str:
    return _p("AI", "za") + _rand(ALNUM + "_-", 35)


def pem_header() -> str:
    return _p("-----BEGIN ", "RSA ", "PRIVATE ", "KEY-----")


def db_password() -> str:
    return _rand(ALNUM, 18)


def postgres_url(pw: str | None = None) -> str:
    return _p("postgres", "://") + f"app_user:{pw or db_password()}@db.internal:5432/prod"


def mysql_url(pw: str | None = None) -> str:
    return _p("mysql", "://") + f"root:{pw or db_password()}@10.0.0.5:3306/shop"


def mongo_url(pw: str | None = None) -> str:
    return _p("mongodb+srv", "://") + f"admin:{pw or db_password()}@cluster0.abcde.mongodb.net/app"


def generic_password() -> str:
    # high-entropy, mixed charset. Re-rolled if a random draw happens to contain a placeholder
    # word (e.g. "here"): such a value would be filtered by design and make tests flaky.
    from leakwatch.scanner.filters import placeholder_reason
    while True:
        v = _rand(ALNUM, 24) + "!" + _rand(string.digits, 3)  # 28 chars: see DEBUG_LOG #8
        if placeholder_reason(v) is None:
            return v


GENERATORS = {
    "FAKE_AWS_KEY": aws_key,
    "FAKE_GHP": github_pat,
    "FAKE_GHO": github_oauth,
    "FAKE_GHS": github_server,
    "FAKE_GITHUB_PAT": github_fine,
    "FAKE_OPENAI": openai_key,
    "FAKE_OPENAI_PROJ": openai_proj,
    "FAKE_ANTHROPIC": anthropic_key,
    "FAKE_STRIPE": stripe_live,
    "FAKE_STRIPE_RK": stripe_restricted,
    "FAKE_SLACK": slack_token,
    "FAKE_GOOGLE": google_key,
    "FAKE_PEM_HEADER": pem_header,
    "FAKE_POSTGRES_URL": postgres_url,
    "FAKE_MYSQL_URL": mysql_url,
    "FAKE_MONGO_URL": mongo_url,
    "FAKE_PASSWORD": generic_password,
}

_TOKEN = re.compile(r"\{\{(FAKE_[A-Z0-9_]+)\}\}")


def fill(template: str) -> tuple[str, dict[str, str]]:
    """Replace every {{FAKE_X}} with a fresh fake; return (text, {name: value})."""
    values: dict[str, str] = {}

    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in values:
            values[name] = GENERATORS[name]()
        return values[name]

    return _TOKEN.sub(sub, template), values
