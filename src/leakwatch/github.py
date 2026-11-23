"""GitHub REST via the Sprites gateway. Writes are restricted to allowlisted repos."""
from __future__ import annotations

import base64
import logging

from .gateway import Gateway, GatewayError

log = logging.getLogger("leakwatch.github")
E2E_PREFIX = "leakwatch-e2e-"
HOOK_NAME_MARK = "leakwatch"  # our hook is identified by its URL containing /github/webhook


class GitHubError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


class GitHub:
    def __init__(self, gw: Gateway, writable: set[str] | list[str]):
        self.gw = gw
        self.writable = {r.lower() for r in writable}

    # ---- plumbing ----------------------------------------------------------------------------
    def _call(self, method: str, path: str, ok=(200, 201, 204), **kw):
        r = self.gw.request("github", method, path,
                            headers={"Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28"}, **kw)
        if r.status_code not in ok:
            msg = ""
            try:
                msg = r.json().get("message", "")
            except ValueError:
                pass
            raise GitHubError(f"{method} {path} -> {r.status_code} {msg}", r.status_code)
        return r.json() if r.content else None

    def _guard(self, repo: str) -> None:
        if repo.lower() not in self.writable:
            raise GitHubError(f"refusing to write to {repo}: not in allowlist")

    # ---- reads -------------------------------------------------------------------------------
    def user(self) -> dict:
        return self._call("GET", "/user")

    def repo(self, repo: str) -> dict:
        return self._call("GET", f"/repos/{repo}")

    def commit(self, repo: str, sha: str) -> dict:
        return self._call("GET", f"/repos/{repo}/commits/{sha}")

    def commits(self, repo: str, n: int = 5, sha: str | None = None) -> list[dict]:
        params = {"per_page": n}
        if sha:
            params["sha"] = sha
        return self._call("GET", f"/repos/{repo}/commits", params=params)

    def issues(self, repo: str, labels: str, state: str = "all") -> list[dict]:
        out, page = [], 1
        while True:
            batch = self._call("GET", f"/repos/{repo}/issues",
                               params={"labels": labels, "state": state, "per_page": 100, "page": page})
            out += [i for i in batch if "pull_request" not in i]
            if len(batch) < 100:
                return out
            page += 1

    def branch_sha(self, repo: str, branch: str) -> str:
        return self._call("GET", f"/repos/{repo}/git/ref/heads/{branch}")["object"]["sha"]

    def hooks(self, repo: str) -> list[dict]:
        return self._call("GET", f"/repos/{repo}/hooks")

    # ---- writes (allowlisted) -------------------------------------------------------------
    def ensure_label(self, repo: str, name: str, color: str = "b60205", desc: str = "") -> None:
        self._guard(repo)
        try:
            self._call("GET", f"/repos/{repo}/labels/{name}")
        except GitHubError as e:
            if e.status != 404:
                raise
            self._call("POST", f"/repos/{repo}/labels", json={"name": name, "color": color,
                                                               "description": desc[:100]})

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> dict:
        self._guard(repo)
        return self._call("POST", f"/repos/{repo}/issues", json={"title": title, "body": body, "labels": labels})

    def commit_comment(self, repo: str, sha: str, body: str, path: str, line: int) -> dict:
        self._guard(repo)
        return self._call("POST", f"/repos/{repo}/commits/{sha}/comments",
                          json={"body": body, "path": path, "line": line})

    def close_issue(self, repo: str, number: int, required_label: str) -> None:
        self._guard(repo)
        issue = self._call("GET", f"/repos/{repo}/issues/{number}")
        if required_label not in {l["name"] for l in issue.get("labels", [])}:
            raise GitHubError(f"refusing to close #{number}: lacks label {required_label}")
        self._call("PATCH", f"/repos/{repo}/issues/{number}", json={"state": "closed", "state_reason": "not_planned"})

    def create_hook(self, repo: str, url: str, secret: str) -> dict:
        self._guard(repo)
        return self._call("POST", f"/repos/{repo}/hooks", json={
            "name": "web", "active": True, "events": ["push"],
            "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": "0"}})

    def update_hook(self, repo: str, hook_id: int, url: str, secret: str) -> dict:
        self._guard(repo)
        return self._call("PATCH", f"/repos/{repo}/hooks/{hook_id}", json={
            "active": True, "events": ["push"],
            "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": "0"}})

    def ping_hook(self, repo: str, hook_id: int) -> None:
        self._guard(repo)
        self._call("POST", f"/repos/{repo}/hooks/{hook_id}/pings")

    # e2e helpers: only branches with the e2e prefix
    def create_branch(self, repo: str, name: str, from_sha: str) -> None:
        self._guard(repo)
        if not name.startswith(E2E_PREFIX):
            raise GitHubError(f"refusing to create branch {name}: must start with {E2E_PREFIX}")
        self._call("POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{name}", "sha": from_sha})

    def delete_branch(self, repo: str, name: str) -> None:
        self._guard(repo)
        if not name.startswith(E2E_PREFIX):
            raise GitHubError(f"refusing to delete branch {name}: must start with {E2E_PREFIX}")
        self._call("DELETE", f"/repos/{repo}/git/refs/heads/{name}")

    def put_file(self, repo: str, branch: str, path: str, content: str, message: str) -> dict:
        """Commit one file on an e2e branch (contents API)."""
        self._guard(repo)
        if not branch.startswith(E2E_PREFIX):
            raise GitHubError(f"refusing to commit to {branch}: must start with {E2E_PREFIX}")
        sha = None
        try:
            sha = self._call("GET", f"/repos/{repo}/contents/{path}", params={"ref": branch})["sha"]
        except GitHubError as e:
            if e.status != 404:
                raise
        body = {"message": message, "branch": branch,
                "content": base64.b64encode(content.encode()).decode()}
        if sha:
            body["sha"] = sha
        return self._call("PUT", f"/repos/{repo}/contents/{path}", json=body)


__all__ = ["GitHub", "GitHubError", "GatewayError", "E2E_PREFIX"]
