import pytest

import fakes
from leakwatch.scanner.filters import path_penalty, placeholder_reason


@pytest.mark.parametrize("value", [
    "your-api-key-here", "changeme", "<your-secret-key>", "xxxxxxxxxxxxxxxx", "${DB_PASSWORD}",
    "{{ token }}", "dummy_token_value_123", "REPLACE_ME_WITH_REAL_SECRET", "placeholder-secret-value",
    "EXAMPLE_KEY_1234567890", "sk-your-key-here", "%(password)s", "null", "aaaaaaaaaaaa",
    "os.environ['X']", "process.env.API_KEY", "redacted-value-0001", "{fakes.stripe_live()}", "{token}",
])
def test_placeholders_detected(value):
    assert placeholder_reason(value) is not None


@pytest.mark.parametrize("gen", [fakes.aws_key, fakes.github_pat, fakes.openai_key,
                                 fakes.generic_password, fakes.db_password, fakes.stripe_live])
def test_real_looking_values_pass(gen):
    for _ in range(50):
        v = gen()
        assert placeholder_reason(v, strict=True) is None, v


def test_path_penalty():
    assert path_penalty("app/config.py") == 1.0
    assert path_penalty("tests/test_x.py") < 1.0
    assert path_penalty("test/a.js") < 1.0
    assert path_penalty("docs/setup.md") < 1.0
    assert path_penalty("src/__tests__/a.ts") < 1.0
    assert path_penalty("config.example.env") < 1.0


def test_bare_call_or_index_is_code_in_any_file():
    from leakwatch.scanner.filters import generic_value_reason
    for v in ["get_token_from_vault()", "cfg['k']", "vault.read(path)"]:
        assert generic_value_reason(v, quoted=False, path="notes.diff") == "code-expression"
    assert generic_value_reason("Zx81kQp0aLmN2", quoted=False, path=".env") is None


def test_strict_filter_never_drops_random_known_format_tokens():
    # Regression for DEBUG_LOG #10: ~1 in 20k random keys used to be dropped as a "placeholder".
    for gen in (fakes.aws_key, fakes.github_pat, fakes.anthropic_key, fakes.openai_proj, fakes.google_key,
                fakes.stripe_live, fakes.slack_token):
        for _ in range(5000):
            v = gen()
            assert placeholder_reason(v, strict=True) is None, (gen.__name__, v[:4])


def test_strict_filter_still_catches_real_placeholders():
    for v in ["AKIA" + "X" * 16, "ghp_" + "x" * 36, fakes._p("AK", "IA") + "EXAMPLEKEY234567",
              "sk-" + "*" * 40, "sk_live_" + "0" * 24, "ghp_REDACTED" + "a1" * 14]:
        assert placeholder_reason(v, strict=True) is not None, v[:6]


def test_strict_your_placeholder_shapes():
    for v in ["sk-proj-your-key-goes-here-1234567890", "ghp_your_token_here_aaaaaaaaaaaaaaaaaaa", "your-api-key"]:
        assert placeholder_reason(v, strict=True) == "placeholder-word:your", v
    assert placeholder_reason("sk-proj-YOUR_keyAbcdefgh", strict=True) is None  # random-looking
