"""Turn findings into GitHub issues (one per real finding, never duplicated) + commit pipeline."""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field

from .config import Config
from .github import E2E_PREFIX, GitHub, GitHubError
from .llm import OpenRouter
from .scanner.detector import Finding, ScanResult, scan_patch
from .store import Store
from .triage import Triage, triage

log = logging.getLogger("leakwatch.reporter")
E2E_LABEL = "leakwatch-e2e"

TYPE_NAMES = {
    "aws_access_key_id": "AWS access key ID", "github_token": "GitHub token",
    "openai_api_key": "OpenAI API key", "anthropic_api_key": "Anthropic API key",
    "stripe_secret_key": "Stripe secret key", "stripe_restricted_key": "Stripe restricted key",
    "slack_token": "Slack token", "google_api_key": "Google API key", "private_key": "private key",
    "database_url": "database password (in a connection URL)", "generic_secret": "secret",
}

UNCLE = {
    "aws_access_key_id": "I'm not mad. I just want you to know that somewhere, a crypto miner is very excited about your AWS account.",
    "github_token": "You committed a GitHub token to GitHub. That's hiding the house key under a mat labelled 'house key'.",
    "openai_api_key": "Somebody is about to have a very productive weekend on your API bill. It won't be you.",
    "anthropic_api_key": "Somebody is about to have a very productive weekend on your API bill. It won't be you.",
    "stripe_secret_key": "This one can move money. I'll wait while you rotate it.",
    "stripe_restricted_key": "Restricted, they said. Restricted to whoever reads your commits, apparently.",
    "slack_token": "Anyone with this can read your Slack. Including the channel where you complain about me.",
    "google_api_key": "Google keys get scraped within minutes of a push. I didn't get these grey hairs from nowhere.",
    "private_key": "A private key is like a toothbrush. You don't share it, and you definitely don't push it.",
    "database_url": "Your database password is in a connection string, in a commit, in a repo. That's three places too many.",
    "generic_secret": "Could be nothing. Could be the password to everything. I didn't get this old by guessing.",
}

ROTATION = {
    "aws_access_key_id": [
        "In the AWS console go to IAM → Users → (the key's user) → Security credentials and **deactivate** the key shown above.",
        "Create a new access key and update it wherever the app reads it (secrets manager, CI variables).",
        "Delete the old key once nothing breaks.",
        "Check CloudTrail for activity from the old key since this commit.",
    ],
    "github_token": [
        "Revoke it: GitHub → Settings → Developer settings → Personal access tokens (or the owning GitHub/OAuth App).",
        "Create a replacement with the minimum scopes and an expiry date.",
        "Review Settings → Security log for use of the old token.",
    ],
    "openai_api_key": ["Revoke the key in the OpenAI dashboard (API keys).", "Create a new key and store it in a secret manager or env var.", "Check usage for unexpected spend since this commit."],
    "anthropic_api_key": ["Disable the key in the Anthropic Console (API keys).", "Create a new key and store it in a secret manager or env var.", "Check usage for unexpected spend since this commit."],
    "stripe_secret_key": ["Roll the key in the Stripe Dashboard → Developers → API keys.", "Update the new key in your deployment secrets.", "Review Developers → Logs and Events for anything you didn't do."],
    "stripe_restricted_key": ["Roll or delete the restricted key in the Stripe Dashboard → Developers → API keys.", "Issue a new restricted key with the same minimal permissions.", "Review Developers → Logs for unexpected calls."],
    "slack_token": ["Revoke/rotate the token on api.slack.com → Your Apps → (app) → OAuth & Permissions.", "Reinstall the app to get a fresh token and update your secrets.", "Check the workspace access logs."],
    "google_api_key": ["Regenerate or delete the key in Google Cloud console → APIs & Services → Credentials.", "Add API and application restrictions to the new key.", "Check billing/usage for unexpected calls."],
    "private_key": ["Generate a new key pair.", "Replace the public key everywhere it is trusted (authorized_keys, deploy keys, certificates) and remove the old one.", "Reissue any certificate tied to the old key."],
    "database_url": ["Change the database user's password (e.g. `ALTER USER … PASSWORD …`).", "Update the connection string in your deployment secrets, not in code.", "Check the database logs and restrict network access to known hosts."],
    "generic_secret": ["Find which system this credential belongs to and change it there.", "Move the new value into a secret manager or environment variable.", "Check that system's logs for use since this commit."],
}

PURGE = """Deleting the line in a new commit is **not** enough: the value stays in git history, in clones and in forks. **Rotate first** — that is what actually fixes it. Then, if you want it out of history:
1. Locally (never commit this file), create `replacements.txt` containing the leaked value followed by `==>REDACTED`.
2. Run `git filter-repo --replace-text replacements.txt` (or BFG Repo-Cleaner), then force-push and ask collaborators to re-clone.
3. If the repo was ever public, ask GitHub Support to purge cached views."""


@dataclass
class Decision:
    report: bool
    reason: str


def decide(f: Finding, t: Triage, cfg: Config) -> Decision:
    if t.verdict == "real":
        return Decision(True, f"verdict real ({t.source})")
    if t.verdict == "placeholder":
        if (f.rule_id != "generic" and t.source.startswith("llm")
                and t.confidence < cfg.llm_placeholder_min_confidence):
            t.verdict, t.why = "unsure", t.why + " (LLM placeholder verdict had low confidence; treated as unsure.)"
        else:
            return Decision(False, f"verdict placeholder ({t.source}, {t.confidence:.2f})")
    if f.confidence >= cfg.report_unsure_min_confidence:
        return Decision(True, f"verdict unsure, rule confidence {f.confidence:.2f}")
    return Decision(False, f"verdict unsure, rule confidence {f.confidence:.2f} < threshold")


def render_issue(f: Finding, t: Triage, repo: str, sha: str, tone: str) -> tuple[str, str]:
    kind = TYPE_NAMES.get(f.secret_type, f.secret_type)
    title = f"🔑 Possible leaked {kind} in {f.file}:{f.line}"
    steps = t.rotation_steps if len(t.rotation_steps) >= 2 else ROTATION.get(f.secret_type, ROTATION["generic_secret"])
    src = "LLM triage" if t.source.startswith("llm") else "rules-only (LLM unavailable)"
    lines = []
    if tone == "security-uncle":
        lines += [f"> 🧓 *{UNCLE.get(f.secret_type, UNCLE['generic_secret'])}*", ""]
    lines += [
        f"**LeakWatch found what looks like a leaked {kind}.**", "",
        "| | |", "|---|---|",
        f"| Commit | [`{sha[:10]}`](https://github.com/{repo}/commit/{sha}) |",
        f"| File | [`{f.file}:{f.line}`](https://github.com/{repo}/blob/{sha}/{f.file}#L{f.line}) |",
        f"| Secret (masked) | `{f.masked}` |",
        f"| Type | {kind} |",
        f"| Verdict | **{t.verdict}** · {src} · confidence {t.confidence:.2f} |",
        f"| Detector | {f.rules_note} (rule confidence {f.confidence:.2f}) |", "",
        "### Why", t.why, "",
        "### Rotate it (do this first)", *[f"{i}. {s}" for i, s in enumerate(steps, 1)], "",
        "### Then purge it from history", PURGE, "",
        "<sub>The masked value shows only the first 4 and last 2 characters. LeakWatch never stores, logs or "
        "sends the full secret: the LLM saw only the masked line, and the database keeps only a SHA-256 "
        "fingerprint, so you'll hear about this secret once.</sub>",
    ]
    if tone == "security-uncle":
        lines += ["", "— your security uncle, LeakWatch"]
    return title, "\n".join(lines)


@dataclass
class CommitReport:
    repo: str
    sha: str
    scanned_files: int = 0
    findings: int = 0
    duplicates: int = 0
    not_reported: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    seconds: float = 0.0


class Pipeline:
    def __init__(self, cfg: Config, gh: GitHub, store: Store, llm: OpenRouter | None):
        self.cfg, self.gh, self.store, self.llm = cfg, gh, store, llm
        self._labels_ok: set[str] = set()

    def _labels(self, repo: str, ref: str | None) -> list[str]:
        labels = list(self.cfg.labels)
        if ref and ref.removeprefix("refs/heads/").startswith(E2E_PREFIX):
            labels.append(E2E_LABEL)
        for name in labels:
            if (repo, name) not in self._labels_ok:
                self.gh.ensure_label(repo, name, "b60205" if name != E2E_LABEL else "cccccc",
                                     "Opened by LeakWatch" if name != E2E_LABEL else "LeakWatch e2e test issue")
                self._labels_ok.add((repo, name))
        return labels

    def scan_commit(self, repo: str, sha: str) -> tuple[ScanResult, dict]:
        commit = self.gh.commit(repo, sha)
        res = ScanResult()
        for f in commit.get("files", []):
            if f.get("status") == "removed":
                continue
            res.extend(scan_patch(f["filename"], f.get("patch")))
        return res, commit

    def process_commit(self, repo: str, sha: str, ref: str | None = None, source: str = "cli") -> CommitReport:
        t0 = time.time()
        rep = CommitReport(repo, sha)
        if not self.cfg.is_watched(repo):
            rep.errors.append("repo not in allowlist")
            self.store.log_run(source, repo, sha, "ignored", "not in allowlist")
            return rep
        try:
            res, commit = self.scan_commit(repo, sha)
            sha = rep.sha = commit.get("sha", sha)
        except GitHubError as e:
            rep.errors.append(str(e))
            self.store.log_run(source, repo, sha, "error", str(e))
            return rep
        rep.scanned_files = len({f for f, _ in res.skipped}) + len({f.file for f in res.findings})
        rep.skipped, rep.findings = res.skipped, len(res.findings)
        for f in res.findings:
            fp = f.fingerprint(repo)
            if self.store.known(fp) is not None:
                rep.duplicates += 1
                continue
            t = triage(f, self.llm)
            d = decide(f, t, self.cfg)
            log.info("%r -> %s (%s)", f, "report" if d.report else "skip", d.reason)
            if not d.report:
                rep.not_reported.append(f"{f.file}:{f.line} {f.secret_type}: {d.reason}")
                continue
            if not self.store.claim(fp, repo, f.file, f.secret_type, sha):
                rep.duplicates += 1
                continue
            title, body = render_issue(f, t, repo, sha, self.cfg.tone)
            try:
                issue = self.gh.create_issue(repo, title, body, self._labels(repo, ref))
                url = issue["html_url"]
            except GitHubError as e:
                if e.status not in (403, 404, 410):
                    self.store.release(fp)
                    rep.errors.append(f"issue create failed: {e}")
                    continue
                try:  # fallback: commit comment on the exact line
                    url = self.gh.commit_comment(repo, sha, f"**{title}**\n\n{body}", f.file, f.line)["html_url"]
                except GitHubError as e2:
                    self.store.release(fp)
                    rep.errors.append(f"issue + comment failed: {e}; {e2}")
                    continue
            self.store.set_issue(fp, url)
            rep.issues.append(url)
        self.store.mark_processed(repo, sha, rep.findings, len(rep.issues))
        rep.seconds = round(time.time() - t0, 2)
        self.store.log_run(source, repo, sha, "ok" if not rep.errors else "partial",
                           f"findings={rep.findings} issues={len(rep.issues)} dup={rep.duplicates} "
                           f"skipped_by_policy={len(rep.not_reported)} {time.time() - t0:.1f}s")
        return rep


def short_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]
