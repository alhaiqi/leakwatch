import pytest

import fakes
from leakwatch.llm import LLMUnavailable
from leakwatch.scanner.detector import scan_patch
from leakwatch.triage import TriageParseError, build_messages, parse, triage


def _f():
    v = fakes.aws_key()
    return scan_patch("app/a.py", f"@@ -0,0 +2 @@\n x = 1\n+AWS_ACCESS_KEY_ID = '{v}'\n").findings[0], v


def test_parse_valid_and_fenced():
    t = parse('```json\n{"verdict":"Real","confidence":0.9,"why":"random","rotation_steps":["a"]}\n```')
    assert (t.verdict, t.confidence, t.rotation_steps) == ("real", 0.9, ["a"])
    assert parse('Sure! {"verdict":"unsure","confidence":0,"why":"?"} hope it helps').verdict == "unsure"


@pytest.mark.parametrize("bad", [
    "no json here", '{"verdict":"maybe","confidence":0.5,"why":"x"}', '{"verdict":"real","confidence":1.5,"why":"x"}',
    '{"verdict":"real","confidence":"high","why":"x"}', '{"verdict":"real","confidence":true,"why":"x"}',
    '{"verdict":"real","confidence":0.5,"why":""}', '{"verdict":"real","confidence":0.5,"why":"x","rotation_steps":"a"}',
    '{"verdict": "real", "confidence": 0.5,', "[1,2]",
])
def test_parse_rejects(bad):
    with pytest.raises(TriageParseError):
        parse(bad)


def test_prompt_never_contains_raw_secret():
    f, v = _f()
    msgs = build_messages(f)
    text = "".join(m["content"] for m in msgs)
    assert v not in text and f.masked in text and "AWS_ACCESS_KEY_ID" in text


class StubLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, messages, models=None):
        self.calls.append(messages)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, "stub:free"

    def free_models(self):
        return ["stub:free"]


def test_retry_once_on_malformed_then_ok():
    f, _ = _f()
    llm = StubLLM(["garbage", '{"verdict":"real","confidence":0.8,"why":"random"}'])
    t = triage(f, llm)
    assert t.verdict == "real" and t.source == "llm:stub:free" and len(llm.calls) == 2


def test_malformed_twice_falls_back_to_rules():
    f, _ = _f()
    t = triage(f, StubLLM(["garbage", "still garbage"]))
    assert t.source == "rules" and t.verdict == "unsure" and t.confidence == f.confidence


def test_unavailable_falls_back_to_rules():
    f, _ = _f()
    assert triage(f, StubLLM([LLMUnavailable("429 everywhere")])).source == "rules"
    assert triage(f, None).source == "rules"


def test_llm_output_is_scrubbed():
    f, _ = _f()
    leaked = fakes.github_pat()
    t = triage(f, StubLLM([f'{{"verdict":"real","confidence":0.9,"why":"like {leaked}","rotation_steps":["revoke {leaked}"]}}']))
    assert leaked not in t.why + "".join(t.rotation_steps)


def test_parse_takes_last_verdict_object_after_thinking():
    text = ('Thinking: features {"length": 16} look like `{"verdict": "real"` maybe...\n'
            'Final: {"verdict":"placeholder","confidence":0.9,"why":"has your marker"}')
    t = parse(text)
    assert t.verdict == "placeholder" and t.confidence == 0.9
