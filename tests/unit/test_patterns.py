import pytest

import fakes
from leakwatch.scanner.patterns import match_generic, match_known

CASES = [
    (fakes.aws_key, "aws_access_key_id"), (fakes.github_pat, "github_token"),
    (fakes.github_oauth, "github_token"), (fakes.github_server, "github_token"),
    (fakes.github_fine, "github_token"), (fakes.openai_key, "openai_api_key"),
    (fakes.openai_proj, "openai_api_key"), (fakes.anthropic_key, "anthropic_api_key"),
    (fakes.stripe_live, "stripe_secret_key"), (fakes.stripe_restricted, "stripe_restricted_key"),
    (fakes.slack_token, "slack_token"), (fakes.google_key, "google_api_key"),
]


@pytest.mark.parametrize("gen,kind", CASES)
@pytest.mark.parametrize("tpl", ['KEY = "{}"', "KEY={}", "  token: '{}'  # prod", "{}"])
def test_known_formats(gen, kind, tpl):
    v = gen()
    hits = match_known(tpl.format(v))
    assert [(h.secret_type, h.value) for h in hits] == [(kind, v)]


def test_anthropic_not_double_counted_as_openai():
    hits = match_known(f"x={fakes.anthropic_key()}")
    assert [h.secret_type for h in hits] == ["anthropic_api_key"]


def test_pem_header():
    hits = match_known(fakes.pem_header())
    assert hits[0].secret_type == "private_key"
    for kind in ("EC ", "OPENSSH ", "", "ENCRYPTED "):
        assert match_known(fakes.pem_header().replace("RSA ", kind))


def test_public_key_header_not_flagged():
    assert match_known(fakes.pem_header().replace("PRIVATE", "PUBLIC")) == []


@pytest.mark.parametrize("gen", [fakes.postgres_url, fakes.mysql_url, fakes.mongo_url])
def test_db_urls_value_is_password(gen):
    pw = fakes.db_password()
    hits = match_known(f'DB = "{gen(pw)}"')
    assert len(hits) == 1 and hits[0].secret_type == "database_url" and hits[0].value == pw


def test_db_url_without_password_not_flagged():
    assert match_known("postgres://db.internal:5432/x") == []
    assert match_known("redis://localhost:6379") == []


def test_near_misses_not_flagged():
    for s in ["AKIA123", "ghp_short", "sk-abc", "sk_test_" + "a" * 24, "xoxb-", "AIzaShort"]:
        assert match_known(s) == [], s


def test_generic_assignment_shapes():
    pw = fakes.generic_password()
    for line in [f'password = "{pw}"', f"DB_PASSWORD={pw}", f"  client_secret: '{pw}'",
                 f'"apiKey": "{pw}",', f"$token = '{pw}';", f"AUTH := \"{pw}\""]:
        hits = match_generic(line)
        assert [h.value for h in hits] == [pw], line


def test_generic_reports_quotedness():
    assert match_generic('password = "abcdefghijk"')[0].quoted is True
    assert match_generic("password = abcdefghijk")[0].quoted is False
