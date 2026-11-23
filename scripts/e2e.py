"""Live end-to-end test against the private test repo, through the real webhook path.

Steps: positive (2 issues, masked, right lines) → negative (no issue) → dedupe (no new issue)
→ robustness (401 on bad signature, non-push ignored). Cleanup always runs and only touches
what this run created (its branch and the issues opened for its commits).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import httpx  # noqa: E402

import fakes  # noqa: E402
from leakwatch import config  # noqa: E402
from leakwatch.cli import public_url, webhook_secret  # noqa: E402
from leakwatch.gateway import Gateway  # noqa: E402
from leakwatch.github import E2E_PREFIX, GitHub  # noqa: E402
from leakwatch.reporter import E2E_LABEL  # noqa: E402

CFG = config.load()
REPO = CFG.repos[0]
GH = GitHub(Gateway(), CFG.repos)
STATE = CFG.data_dir / "e2e-state.json"
WAIT = 60


def log(msg: str) -> None:
    print(f"[e2e {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st))


def processed(sha: str) -> bool:
    db = sqlite3.connect(CFG.data_dir / "leakwatch.db")
    try:
        return db.execute("SELECT 1 FROM processed WHERE repo=? AND sha=?", (REPO, sha)).fetchone() is not None
    finally:
        db.close()


def last_run_detail(sha: str) -> str:
    db = sqlite3.connect(CFG.data_dir / "leakwatch.db")
    try:
        row = db.execute("SELECT detail FROM runs WHERE repo=? AND sha=? ORDER BY id DESC LIMIT 1", (REPO, sha)).fetchone()
        return row[0] if row else ""
    finally:
        db.close()


def issues_for(sha: str) -> list[dict]:
    """Issues LeakWatch opened for this commit. Source of truth = the server's DB (written before
    `processed`), then GET /issues/{n} (strongly consistent; the list endpoint lags; DEBUG_LOG #7)."""
    db = sqlite3.connect(CFG.data_dir / "leakwatch.db")
    try:
        urls = [r[0] for r in db.execute("SELECT issue_url FROM fingerprints WHERE repo=? AND commit_sha=? "
                                         "AND issue_url LIKE '%/issues/%'", (REPO, sha))]
    finally:
        db.close()
    return [GH._call("GET", f"/repos/{REPO}/issues/{u.rsplit('/', 1)[1]}") for u in urls]


def wait_processed(sha: str, timeout: int = WAIT) -> float:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if processed(sha):
            return time.time() - t0
        time.sleep(1)
    raise AssertionError(f"commit {sha[:10]} not processed within {timeout}s (webhook not delivered?)")


def commit(st: dict, path: str, content: str, msg: str) -> str:
    sha = GH.put_file(REPO, st["branch"], path, content, msg)["commit"]["sha"]
    st["commits"].append(sha)
    save_state(st)
    return sha


def track_issues(st: dict, sha: str) -> list[dict]:
    found = issues_for(sha)
    for i in found:
        if i["number"] not in st["issues"]:
            st["issues"].append(i["number"])
    save_state(st)
    return found


def cleanup(st: dict) -> None:
    time.sleep(3)  # let an in-flight commit finish so its issues are recorded
    for sha in st.get("commits", []):  # pick up issues that may have landed after an assertion failed
        try:
            track_issues(st, sha)
        except Exception as e:
            log(f"cleanup: issue lookup for {sha[:10]} failed: {e}")
    for n in st.get("issues", []):
        try:
            GH.close_issue(REPO, n, E2E_LABEL)
            log(f"cleanup: closed #{n}")
        except Exception as e:
            log(f"cleanup: close #{n} failed: {e}")
    if st.get("branch", "").startswith(E2E_PREFIX):
        try:
            GH.delete_branch(REPO, st["branch"])
            log(f"cleanup: deleted branch {st['branch']}")
        except Exception as e:
            log(f"cleanup: delete branch failed: {e}")
    STATE.unlink(missing_ok=True)


def run() -> dict:
    ts = time.strftime("%Y%m%d-%H%M%S")
    st = {"branch": f"{E2E_PREFIX}{ts}", "commits": [], "issues": []}
    save_state(st)
    res = {"run": ts, "steps": {}, "issues": [], "ok": False}
    url = public_url().rstrip("/") + "/github/webhook"
    try:
        GH.create_branch(REPO, st["branch"], GH.branch_sha(REPO, GH.repo(REPO)["default_branch"]))
        log(f"branch {st['branch']}")

        # 1. positive -------------------------------------------------------------------------
        aws, pw = fakes.aws_key(), fakes.db_password()
        pg = fakes.postgres_url(pw)
        path = f"e2e/{ts}/settings.py"
        content = f'"""e2e fixture: values are fake, generated at runtime"""\nimport os\n\nAWS_ACCESS_KEY_ID = "{aws}"\nDATABASE_URL = "{pg}"\nTIMEOUT = 30\n'
        t0 = time.time()
        sha1 = commit(st, path, content, "e2e: positive")
        waited = wait_processed(sha1)
        got = track_issues(st, sha1)
        elapsed = time.time() - t0
        blob = "".join(i["title"] + i["body"] for i in got)
        lines = sorted(int(i["title"].rsplit(":", 1)[1]) for i in got)
        assert len(got) == 2, f"expected exactly 2 issues, got {len(got)}"
        assert aws not in blob and pw not in blob and pg not in blob, "full fake value leaked into an issue"
        assert all(path in i["title"] for i in got), "wrong file in title"
        assert lines == [4, 5], f"wrong lines {lines}"
        assert aws[:4] + "…" + aws[-2:] in blob, "masked AWS value missing"
        res["steps"]["positive"] = {"pass": True, "seconds_to_issues": round(elapsed, 1),
                                    "issues": [i["html_url"] for i in got], "lines": lines}
        log(f"1 positive PASS: 2 issues in {elapsed:.1f}s, lines {lines}, masked")

        # 2. negative -------------------------------------------------------------------------
        sha2 = commit(st, f"e2e/{ts}/config.example.env", "API_KEY=your-api-key-here\nPASSWORD=changeme\n", "e2e: placeholders")
        waited = wait_processed(sha2)
        got2 = track_issues(st, sha2)
        assert got2 == [], f"placeholders produced {len(got2)} issue(s)"
        res["steps"]["negative"] = {"pass": True, "seconds_to_processed": round(waited, 1)}
        log(f"2 negative PASS: no issue ({waited:.1f}s to processed)")

        # 3. dedupe: re-add the same key line (modified) in the same file -------------------
        content3 = content.replace(f'"{aws}"', f'"{aws}"  # still here').replace("TIMEOUT = 30", "TIMEOUT = 60")
        sha3 = commit(st, path, content3, "e2e: same key again")
        waited = wait_processed(sha3)
        got3 = track_issues(st, sha3)
        detail = last_run_detail(sha3)
        assert got3 == [], f"duplicate produced {len(got3)} issue(s)"
        assert "dup=1" in detail, f"expected the key to be seen and deduped, run detail: {detail}"
        res["steps"]["dedupe"] = {"pass": True, "run_detail": detail}
        log(f"3 dedupe PASS: no new issue ({detail})")

        # 4. robustness -----------------------------------------------------------------------
        body = json.dumps({"ref": "refs/heads/x", "repository": {"full_name": REPO}, "commits": []}).encode()
        r_bad = httpx.post(url, content=body, timeout=15, headers={
            "X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=" + "0" * 64, "Content-Type": "application/json"})
        sig = "sha256=" + hmac.new(webhook_secret(CFG).encode(), b'{"action":"opened"}', hashlib.sha256).hexdigest()
        r_ev = httpx.post(url, content=b'{"action":"opened"}', timeout=15, headers={
            "X-GitHub-Event": "issues", "X-Hub-Signature-256": sig, "Content-Type": "application/json"})
        assert r_bad.status_code == 401, f"bad signature got {r_bad.status_code}"
        assert r_ev.status_code == 202 and r_ev.json().get("status") == "ignored", f"non-push got {r_ev.status_code} {r_ev.text}"
        res["steps"]["robustness"] = {"pass": True, "bad_signature": r_bad.status_code, "non_push": r_ev.json()}
        log("4 robustness PASS: 401 on bad signature, non-push ignored")
        res["ok"] = True
    except AssertionError as e:
        res["error"] = str(e)
        log(f"FAIL: {e}")
    finally:
        res["issues"] = [f"https://github.com/{REPO}/issues/{n}" for n in st["issues"]]
        cleanup(st)
        res["cleanup"] = "done"
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup-only", action="store_true", help="clean up a previous run's state file")
    a = ap.parse_args()
    if a.cleanup_only:
        if STATE.exists():
            cleanup(json.loads(STATE.read_text()))
        return 0
    res = run()
    out = CFG.data_dir / "e2e-results"
    out.mkdir(exist_ok=True)
    (out / f"{res['run']}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
