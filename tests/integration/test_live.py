"""Live tests: real Sprites gateway → GitHub / OpenRouter. Run: pytest -m live"""
import pytest

import fakes
from leakwatch import config
from leakwatch.gateway import Gateway
from leakwatch.llm import LLMUnavailable, OpenRouter
from leakwatch.scanner.detector import Finding, scan_patch
from leakwatch.scanner.redact import mask
from leakwatch.triage import triage

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def llm():
    cfg = config.load()
    return OpenRouter(Gateway(), cfg.preferred_models, cfg.max_models_to_try, cfg.llm_timeout, cfg.llm_max_tokens)


def test_gateway_github_smoke():
    gw = Gateway()
    r = gw.request("github", "GET", "/user")
    assert r.status_code == 200 and "repo" in r.headers.get("x-oauth-scopes", "")


def test_only_free_models(llm):
    models = llm.free_models(refresh=True)
    assert models and all(m.endswith(":free") for m in models)


def test_placeholder_sk_your_key_here_is_not_real(llm):
    v = "sk-your-key-here"
    f = Finding("openai_api_key", "generic", "config.example.env", 8, mask(v), 0.6,
                [f"OPENAI_API_KEY={mask(v)}"], "value assigned to `OPENAI_API_KEY`", _secret=v)
    t = triage(f, llm)
    print("triage:", t)
    assert t.source.startswith("llm:"), "LLM must have answered (not rules fallback)"
    assert t.verdict in ("placeholder", "unsure") and t.verdict != "real"


def test_random_aws_key_is_not_placeholder(llm):
    v = fakes.aws_key()
    f = scan_patch("app/settings.py", f"@@ -0,0 +3 @@\n REGION = 'eu-west-1'\n+AWS_ACCESS_KEY_ID = '{v}'\n").findings[0]
    t = triage(f, llm)
    print("triage:", t)
    assert t.source.startswith("llm:") and t.verdict in ("real", "unsure")


def test_forced_failure_raises_unavailable():
    broken = OpenRouter(Gateway(), [], max_models=2)
    with pytest.raises(LLMUnavailable):
        broken.complete([{"role": "user", "content": "hi"}], models=["leakwatch/does-not-exist:free"])
