import pytest

import fakes
from leakwatch.scanner.filters import path_penalty, placeholder_reason


@pytest.mark.parametrize("value", [
    "your-api-key-here", "changeme", "<your-secret-key>", "xxxxxxxxxxxxxxxx", "${DB_PASSWORD}",
    "{{ token }}", "dummy_token_value_123", "REPLACE_ME_WITH_REAL_SECRET", "placeholder-secret-value",
    "EXAMPLE_KEY_1234567890", "sk-your-key-here", "%(password)s", "null", "aaaaaaaaaaaa",
    "os.environ['X']", "process.env.API_KEY", "redacted-value-0001",
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
