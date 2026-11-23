import fakes
from leakwatch.config import Config
from leakwatch.reporter import Pipeline, decide, render_issue
from leakwatch.scanner.detector import scan_patch
from leakwatch.store import Store
from leakwatch.triage import Triage

CFG = Config(repos=["o/r"])


def _f(path="app/a.py", gen=fakes.aws_key):
    v = gen()
    return scan_patch(path, f"@@ -0,0 +1 @@\n+K = '{v}'\n").findings[0], v


def test_decide_policy():
    f, _ = _f()
    assert decide(f, Triage("real", .9, "x", source="llm:m"), CFG).report
    assert decide(f, Triage("unsure", .5, "x"), CFG).report            # rule conf 0.9 >= 0.8
    assert not decide(f, Triage("placeholder", .95, "x", source="llm:m"), CFG).report
    assert decide(f, Triage("placeholder", .4, "x", source="llm:m"), CFG).report   # low-conf LLM can't suppress
    t, _ = _f("tests/a.py")
    assert not decide(t, Triage("unsure", .5, "x"), CFG).report        # 0.54 < 0.8
    g = scan_patch("a.js", "@@ -0,0 +1 @@\n+const password = 'Qm9x2LkPz81vRt!7'\n").findings[0]
    assert not decide(g, Triage("placeholder", .3, "x", source="llm:m"), CFG).report  # generic: LLM decides


def test_render_issue_masked_and_complete():
    f, v = _f()
    title, body = render_issue(f, Triage("real", .9, "Looks random.", ["a", "b"], "llm:m"), "o/r", "a" * 40, "security-uncle")
    assert title == f"🔑 Possible leaked AWS access key ID in app/a.py:1"
    assert v not in title + body and f.masked in body
    for s in ("a" * 40, "app/a.py", "Rotate it", "purge it from history", "1. a", "security uncle"):
        assert s in body
    _, prof = render_issue(f, Triage("real", .9, "x"), "o/r", "a" * 40, "professional")
    assert "uncle" not in prof and "🧓" not in prof


class FakeGH:
    def __init__(self, files):
        self.files, self.issues = files, []

    def commit(self, repo, sha):
        return {"sha": sha, "files": self.files}

    def ensure_label(self, *a, **k):
        pass

    def create_issue(self, repo, title, body, labels):
        self.issues.append((title, body, labels))
        return {"html_url": f"https://gh/{len(self.issues)}"}


def test_pipeline_dedupes_across_commits(tmp_path):
    v = fakes.aws_key()
    gh = FakeGH([{"filename": "a.py", "status": "added", "patch": f"@@ -0,0 +1 @@\n+K='{v}'\n"}])
    p = Pipeline(CFG, gh, Store(tmp_path / "d.db"), None)
    r1 = p.process_commit("o/r", "s1", ref="refs/heads/leakwatch-e2e-x")
    r2 = p.process_commit("o/r", "s2")
    assert len(r1.issues) == 1 and r2.duplicates == 1 and len(gh.issues) == 1
    assert "leakwatch-e2e" in gh.issues[0][2]
    assert v not in gh.issues[0][0] + gh.issues[0][1]


def test_pipeline_ignores_unwatched_repo(tmp_path):
    p = Pipeline(CFG, FakeGH([]), Store(tmp_path / "d.db"), None)
    assert p.process_commit("evil/repo", "s").errors == ["repo not in allowlist"]
