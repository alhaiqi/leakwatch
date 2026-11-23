"""Publish this repo's git history to the public submission repo via the GitHub connector
(Git Data API: blobs → trees → commits → refs). No `gh`, no token, no force-push.

Guards: target must be the submission repo; working tree clean; self-scan of HEAD clean.
Replays every local commit (message + author date preserved). Idempotent: data/publish-map.json
maps local → remote commits, so later runs only replay new commits (fast-forward only).
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from leakwatch.gateway import Gateway  # noqa: E402
from leakwatch.github import GitHub, GitHubError  # noqa: E402
from leakwatch.scanner.detector import scan_text  # noqa: E402
from leakwatch.scanner.diff import should_skip  # noqa: E402

TARGET = "alhaiqi/leakwatch"
MAP = ROOT / "data" / "publish-map.json"


def git(*args: str, binary: bool = False):
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True)
    return out.stdout if binary else out.stdout.decode()


def self_scan_head() -> int:
    hits = 0
    for path in git("ls-tree", "-r", "--name-only", "HEAD").split("\n"):
        if not path or should_skip(path, ""):
            continue
        try:
            text = git("show", f"HEAD:{path}", binary=True).decode()
        except UnicodeDecodeError:
            continue
        for f in scan_text(path, text).findings:
            print(f"  self-scan FOUND {f.secret_type} {f.file}:{f.line} {f.masked}")
            hits += 1
    return hits


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] != TARGET:
        raise SystemExit(f"refusing: only {TARGET} may be published to")
    if git("status", "--porcelain").strip():
        raise SystemExit("refusing: working tree not clean; commit first")
    if self_scan_head():
        raise SystemExit("refusing: self-scan of HEAD is not clean")
    print("self-scan of HEAD: CLEAN")

    gh = GitHub(Gateway(), [TARGET])
    call = gh._call
    mapping: dict[str, str] = json.loads(MAP.read_text()) if MAP.exists() else {}
    repo = call("GET", f"/repos/{TARGET}")
    branch = repo["default_branch"] or "main"

    remote_head = None
    try:
        remote_head = call("GET", f"/repos/{TARGET}/git/ref/heads/{branch}")["object"]["sha"]
    except GitHubError as e:
        if e.status not in (404, 409):
            raise
    if remote_head is None:  # empty repo: Git Data API returns 409 until a first commit exists
        boot = call("PUT", f"/repos/{TARGET}/contents/README.md", json={
            "message": "Initialize repository (bootstrap for Git Data API)",
            "content": base64.b64encode(b"# LeakWatch\n\nPublishing...\n").decode(), "branch": branch})
        remote_head = boot["commit"]["sha"]
        mapping["__bootstrap__"] = remote_head
        print(f"bootstrapped empty repo with {remote_head[:10]}")

    blobs_done: set[str] = set(mapping.get("__blobs__", []))
    parent = remote_head
    local_commits = git("rev-list", "--reverse", "HEAD").split()
    for c in local_commits:
        if c in mapping:
            parent = mapping[c]
            continue
        entries = []
        for line in git("ls-tree", "-r", c).strip().split("\n"):
            meta, path = line.split("\t", 1)
            mode, typ, sha = meta.split()
            if sha not in blobs_done:
                data = git("cat-file", "blob", sha, binary=True)
                got = call("POST", f"/repos/{TARGET}/git/blobs",
                           json={"content": base64.b64encode(data).decode(), "encoding": "base64"})["sha"]
                assert got == sha, f"blob sha mismatch for {path}"
                blobs_done.add(sha)
            entries.append({"path": path, "mode": mode, "type": typ, "sha": sha})
        tree = call("POST", f"/repos/{TARGET}/git/trees", json={"tree": entries})["sha"]
        assert tree == git("rev-parse", f"{c}^{{tree}}").strip(), "tree sha mismatch"
        name, email, date = git("log", "-1", "--format=%an%x00%ae%x00%aI", c).strip().split("\x00")
        msg = git("log", "-1", "--format=%B", c).strip() + f"\n\n(Published from local commit {c[:12]} via the Sprites GitHub connector.)"
        new = call("POST", f"/repos/{TARGET}/git/commits", json={
            "message": msg, "tree": tree, "parents": [parent],
            "author": {"name": name, "email": email, "date": date}})["sha"]
        mapping[c] = parent = new
        mapping["__blobs__"] = sorted(blobs_done)
        MAP.write_text(json.dumps(mapping, indent=1))
        print(f"  {c[:10]} -> {new[:10]}  {msg.splitlines()[0][:60]}")

    call("PATCH", f"/repos/{TARGET}/git/refs/heads/{branch}", json={"sha": parent, "force": False})
    print(f"{branch} -> {parent[:10]} (fast-forward)")
    for tag in git("tag", "--list", "milestone-*").split():
        local = git("rev-list", "-n1", tag).strip()
        if local not in mapping:
            continue
        try:
            call("POST", f"/repos/{TARGET}/git/refs", json={"ref": f"refs/tags/{tag}", "sha": mapping[local]})
            print(f"  tag {tag}")
        except GitHubError as e:
            if e.status != 422:  # 422 = tag already exists: leave it (no forced ref updates)
                raise
    print(f"published: https://github.com/{TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
