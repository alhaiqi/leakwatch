"""Push demo commits to the test repo through the API (for the demo video and MANUAL_TEST.md).

  demo_seed.py leak         commit a freshly generated FAKE AWS key   -> expect 1 issue
  demo_seed.py placeholder  commit an example env file                -> expect no issue
  demo_seed.py duplicate    re-add the same leaked line in a new commit -> expect no new issue
  demo_seed.py cleanup      close the demo issues, delete the demo branch
Add --wait N to wait until the running LeakWatch service has processed the commit.
The fake key is never stored locally: `duplicate` re-reads the line from GitHub.
"""
from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import fakes  # noqa: E402
from leakwatch import config  # noqa: E402
from leakwatch.gateway import Gateway  # noqa: E402
from leakwatch.github import GitHub  # noqa: E402
from leakwatch.reporter import E2E_LABEL  # noqa: E402

CFG = config.load()
REPO = CFG.repos[0]
GH = GitHub(Gateway(), CFG.repos)
STATE = CFG.data_dir / "demo-state.json"   # holds branch name + commit SHAs only
PATH = "app/settings.py"


def state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    st = {"branch": f"leakwatch-e2e-demo-{time.strftime('%Y%m%d-%H%M%S')}", "commits": []}
    GH.create_branch(REPO, st["branch"], GH.branch_sha(REPO, GH.repo(REPO)["default_branch"]))
    STATE.write_text(json.dumps(st))
    print(f"created branch {st['branch']}")
    return st


def current(st: dict, path: str) -> str:
    d = GH._call("GET", f"/repos/{REPO}/contents/{path}", params={"ref": st["branch"]})
    return base64.b64decode(d["content"]).decode()


def push(st: dict, path: str, content: str, msg: str) -> str:
    sha = GH.put_file(REPO, st["branch"], path, content, msg)["commit"]["sha"]
    st["commits"].append(sha)
    STATE.write_text(json.dumps(st))
    print(f"pushed {sha[:10]} ({msg}) on {st['branch']}")
    return sha


def wait(sha: str, timeout: int) -> None:
    db_path = CFG.data_dir / "leakwatch.db"
    t0 = time.time()
    while time.time() - t0 < timeout:
        db = sqlite3.connect(db_path)
        try:
            done = db.execute("SELECT 1 FROM processed WHERE repo=? AND sha=?", (REPO, sha)).fetchone()
            if done:
                urls = [r[0] for r in db.execute("SELECT issue_url FROM fingerprints WHERE commit_sha=?", (sha,))]
                detail = db.execute("SELECT detail FROM runs WHERE sha=? ORDER BY id DESC LIMIT 1", (sha,)).fetchone()
                print(f"processed after {time.time() - t0:.0f}s: {detail[0] if detail else ''}")
                for u in urls:
                    print(f"  issue: {u}")
                if not urls:
                    print("  no new issue")
                return
        finally:
            db.close()
        time.sleep(1)
    raise SystemExit(f"not processed within {timeout}s — is the 'leakwatch' service running? (leakwatch doctor)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["leak", "placeholder", "duplicate", "cleanup"])
    ap.add_argument("--wait", type=int, default=0, metavar="SECONDS")
    a = ap.parse_args()
    if a.mode == "cleanup":
        if not STATE.exists():
            print("nothing to clean up")
            return 0
        st = json.loads(STATE.read_text())
        db = sqlite3.connect(CFG.data_dir / "leakwatch.db")
        for sha in st["commits"]:
            for (u,) in db.execute("SELECT issue_url FROM fingerprints WHERE commit_sha=? AND issue_url LIKE '%/issues/%'", (sha,)):
                GH.close_issue(REPO, int(u.rsplit("/", 1)[1]), E2E_LABEL)
                print(f"closed {u}")
        GH.delete_branch(REPO, st["branch"])
        print(f"deleted branch {st['branch']}")
        STATE.unlink()
        return 0
    st = state()
    if a.mode == "leak":
        sha = push(st, PATH, f'import os\n\nREGION = "eu-west-1"\nAWS_ACCESS_KEY_ID = "{fakes.aws_key()}"\nTIMEOUT = 30\n',
                   "Add AWS settings")
    elif a.mode == "placeholder":
        sha = push(st, "config.example.env", "API_KEY=your-api-key-here\nPASSWORD=changeme\n", "Add example env file")
    else:
        lines = current(st, PATH).split("\n")
        lines = [l + "  # same key" if l.startswith("AWS_ACCESS_KEY_ID") else l for l in lines]
        sha = push(st, PATH, "\n".join(lines).replace("TIMEOUT = 30", "TIMEOUT = 60"),
                   "Tweak timeout (same key line re-added)")
    if a.wait:
        wait(sha, a.wait)
    return 0


if __name__ == "__main__":
    sys.exit(main())
