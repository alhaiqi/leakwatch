"""`leakwatch` command line: doctor, serve, register-webhook, scan-commit, scan-recent, self-scan."""
from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import config as config_mod
from .gateway import Gateway, GatewayError
from .github import GitHub, GitHubError
from .llm import OpenRouter
from .reporter import Pipeline
from .scanner.detector import scan_text
from .scanner.diff import should_skip
from .scanner.redact import scrub
from .store import Store

SERVICE_NAME = "leakwatch"
TOKEN_ENV_VARS = ("GITHUB_TOKEN", "GH_TOKEN", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


class ScrubFilter(logging.Filter):
    """Defense in depth: every log line passes through the secret scrubber."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = scrub(record.getMessage()), ()
        return True


def setup_logging(level: str = "INFO") -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    h.addFilter(ScrubFilter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class Ctx:
    cfg: config_mod.Config
    gw: Gateway
    gh: GitHub
    store: Store
    llm: OpenRouter | None
    pipeline: Pipeline


def make_ctx(cfg: config_mod.Config | None = None) -> Ctx:
    cfg = cfg or config_mod.load()
    data = config_mod.ensure_data_dir(cfg)
    gw = Gateway(cache_file=data / "gateway-cache.json")
    gh = GitHub(gw, cfg.repos)
    store = Store(data / "leakwatch.db")
    llm = (OpenRouter(gw, cfg.preferred_models, cfg.max_models_to_try, cfg.llm_timeout, cfg.llm_max_tokens)
           if cfg.llm_enabled else None)
    return Ctx(cfg, gw, gh, store, llm, Pipeline(cfg, gh, store, llm))


def webhook_secret(cfg: config_mod.Config) -> str:
    p = config_mod.ensure_data_dir(cfg) / "webhook_secret"
    if not p.exists():
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    os.chmod(p, 0o600)
    return p.read_text().strip()


def sprite_info() -> dict:
    try:
        return json.loads(subprocess.run(["sprite-env", "info"], capture_output=True, text=True, timeout=10).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def public_url() -> str | None:
    return os.environ.get("LEAKWATCH_PUBLIC_URL") or sprite_info().get("sprite_url")


def hook_url() -> str:
    base = public_url()
    if not base:
        raise SystemExit("cannot determine public URL (sprite-env info failed; set LEAKWATCH_PUBLIC_URL)")
    return base.rstrip("/") + "/github/webhook"


# ---- commands -------------------------------------------------------------------------------
def print_report(rep) -> None:
    print(f"{rep.repo}@{rep.sha[:10]}: findings={rep.findings} new_issues={len(rep.issues)} "
          f"duplicates={rep.duplicates} in {rep.seconds}s")
    for u in rep.issues:
        print(f"  issue: {u}")
    for n in rep.not_reported:
        print(f"  not reported: {n}")
    for f, why in rep.skipped:
        print(f"  skipped: {f} ({why})")
    for e in rep.errors:
        print(f"  ERROR: {e}")


def cmd_scan_commit(a) -> int:
    ctx = make_ctx()
    rep = ctx.pipeline.process_commit(a.repo, a.sha, ref=a.ref, source="cli")
    print_report(rep)
    return 1 if rep.errors else 0


def cmd_scan_recent(a) -> int:
    ctx = make_ctx()
    rc = 0
    for c in reversed(ctx.gh.commits(a.repo, a.n, a.branch)):
        rep = ctx.pipeline.process_commit(a.repo, c["sha"], source="cli-recent")
        print_report(rep)
        rc |= bool(rep.errors)
    return rc


def cmd_register_webhook(a) -> int:
    ctx = make_ctx()
    url, secret = hook_url(), webhook_secret(ctx.cfg)
    for repo in ([a.repo] if a.repo else ctx.cfg.repos):
        ours = [h for h in ctx.gh.hooks(repo) if h.get("config", {}).get("url", "").endswith("/github/webhook")]
        if not ours:
            h = ctx.gh.create_hook(repo, url, secret)
            print(f"{repo}: created hook {h['id']} -> {url}")
        else:
            h = ctx.gh.update_hook(repo, ours[0]["id"], url, secret)
            print(f"{repo}: updated hook {h['id']} -> {url}")
            for extra in ours[1:]:
                print(f"{repo}: WARNING extra LeakWatch-looking hook {extra['id']} left untouched")
    return 0


def cmd_serve(a) -> int:
    from .server import run
    run(make_ctx(), webhook_secret(config_mod.load()), poll=a.poll)
    return 0


def iter_repo_files(root: Path):
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
                         capture_output=True, text=True)
    files = out.stdout.split() if out.returncode == 0 else [
        str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    for rel in files:
        yield rel, root / rel


def cmd_self_scan(a) -> int:
    root = Path(a.path).resolve()
    total, hits = 0, []
    for rel, p in iter_repo_files(root):
        if should_skip(rel, "") or not p.is_file():
            continue
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        total += 1
        hits += scan_text(rel, text).findings
    for f in hits:
        print(f"  FOUND {f.secret_type} {f.file}:{f.line} {f.masked} ({f.rules_note})")
    print(f"self-scan: {total} files, {len(hits)} findings -> {'CLEAN' if not hits else 'NOT CLEAN'}")
    return 1 if hits else 0


def heartbeat_summary(path: Path) -> str:
    if not path.exists():
        return "no heartbeat log yet"
    rows = [l.split() for l in path.read_text().splitlines() if len(l.split()) == 4]
    if not rows:
        return "empty heartbeat log"
    pauses = restarts = boots = 0
    for prev, cur in zip(rows, rows[1:]):
        gap = float(cur[0]) - float(prev[0])
        if cur[3] != prev[3]:
            boots += 1
        elif cur[2] != prev[2]:
            restarts += 1
        elif gap > 120:
            pauses += 1
    return (f"{len(rows)} beats since {time.strftime('%Y-%m-%d %H:%MZ', time.gmtime(float(rows[0][0])))}; "
            f"pauses(gap>120s, same pid)={pauses} process-restarts={restarts} reboots(new boot_id)={boots}")


def cmd_doctor(a) -> int:
    results: list[tuple[bool, str, str]] = []

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # doctor must never crash
            ok, detail = False, f"{type(e).__name__}: {scrub(str(e))[:200]}"
        results.append((ok, name, detail))
        print(f"{'✅' if ok else '❌'} {name}: {detail}", flush=True)
        return ok

    cfg = config_mod.load()
    check("config", lambda: (bool(cfg.repos), f"watching {', '.join(cfg.repos) or 'NOTHING'}; tone={cfg.tone}"))
    check("no tokens in environment", lambda: (
        not [v for v in TOKEN_ENV_VARS if os.environ.get(v)],
        "none of " + "/".join(TOKEN_ENV_VARS) + " set" if not [v for v in TOKEN_ENV_VARS if os.environ.get(v)]
        else "SET: " + ", ".join(v for v in TOKEN_ENV_VARS if os.environ.get(v))))
    data = config_mod.ensure_data_dir(cfg)
    secret_p = data / "webhook_secret"
    check("data dir permissions", lambda: (
        (data.stat().st_mode & 0o077) == 0 and (not secret_p.exists() or (secret_p.stat().st_mode & 0o077) == 0),
        f"{data} mode {oct(data.stat().st_mode & 0o777)}"
        + (f", webhook_secret mode {oct(secret_p.stat().st_mode & 0o777)}" if secret_p.exists() else ", no webhook secret yet")))
    gw = Gateway(cache_file=data / "gateway-cache.json")
    check("gateway discovery", lambda: (
        {"github", "openrouter"} <= set(gw.connections(refresh=True)),
        "connections: " + ", ".join(sorted(gw.connections()))))
    gh = GitHub(gw, cfg.repos)

    def gh_user():
        r = gw.request("github", "GET", "/user")
        scopes = r.headers.get("x-oauth-scopes", "")
        return r.status_code == 200 and "repo" in scopes, f"login={r.json().get('login')} scopes=[{scopes}]"
    check("GitHub connector", gh_user)
    for repo in cfg.repos:
        check(f"repo {repo}", lambda repo=repo: (lambda r: (True, f"private={r['private']} issues={r['has_issues']}"))(gh.repo(repo)))
    llm = OpenRouter(gw, cfg.preferred_models)
    check("OpenRouter connector (free models)", lambda: (
        lambda m: (len(m) > 0, f"{len(m)} free models; first: {', '.join(m[:3])}"))(llm.free_models()))
    if a.deep:
        check("OpenRouter completion", lambda: (lambda t: (True, f"{t[1]} replied {t[0].strip()[:20]!r}"))(
            llm.complete([{"role": "user", "content": "Reply with OK"}])))
    if not a.offline_service:
        def svc():
            out = subprocess.run(["sprite-env", "services", "get", SERVICE_NAME], capture_output=True, text=True)
            st = json.loads(out.stdout or "{}").get("state", {})
            return st.get("status") == "running", f"service '{SERVICE_NAME}' status={st.get('status')} restarts={st.get('restart_count', 0)}"
        check("Sprite service", svc)

        def health():
            import httpx
            url = (public_url() or "").rstrip("/") + "/healthz"
            r = httpx.get(url, timeout=15)
            return r.status_code == 200, f"GET {url} -> {r.status_code} {r.text.strip()[:60]}"
        check("public URL /healthz", health)

        def hooks():
            msgs, ok = [], True
            for repo in cfg.repos:
                ours = [h for h in gh.hooks(repo) if h.get("config", {}).get("url", "").endswith("/github/webhook")]
                last = ours[0].get("last_response", {}) if ours else {}
                ok &= len(ours) == 1 and ours[0].get("active") and ours[0]["config"]["url"] == hook_url()
                msgs.append(f"{repo}: {len(ours)} hook(s), last delivery {last.get('code')} {last.get('status', '')}")
            return ok, "; ".join(msgs)
        check("webhook registered", hooks)
        check("heartbeat (sleep/wake evidence)", lambda: (True, heartbeat_summary(data / "heartbeat.log")))
    failed = [n for ok, n, _ in results if not ok]
    print(f"\ndoctor: {len(results) - len(failed)}/{len(results)} checks green" + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="leakwatch", description="Watch GitHub pushes for leaked secrets.")
    p.add_argument("--log-level", default=os.environ.get("LEAKWATCH_LOG_LEVEL", "INFO"))
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="check connectors, config, service, webhook")
    d.add_argument("--deep", action="store_true", help="also run a tiny LLM completion")
    d.add_argument("--offline-service", action="store_true", help="skip service/webhook/public-URL checks")
    d.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("serve", help="run the webhook server on :8080")
    s.add_argument("--poll", type=int, default=0, metavar="SECONDS", help="fallback: poll commits instead of webhooks")
    s.set_defaults(fn=cmd_serve)
    r = sub.add_parser("register-webhook", help="create or update the single LeakWatch hook")
    r.add_argument("repo", nargs="?")
    r.set_defaults(fn=cmd_register_webhook)
    c = sub.add_parser("scan-commit", help="scan one commit and report")
    c.add_argument("repo"); c.add_argument("sha")
    c.add_argument("--ref", help="branch the commit is on (e2e branches get the leakwatch-e2e label)")
    c.set_defaults(fn=cmd_scan_commit)
    n = sub.add_parser("scan-recent", help="scan the last N commits")
    n.add_argument("repo"); n.add_argument("--n", type=int, default=5); n.add_argument("--branch")
    n.set_defaults(fn=cmd_scan_recent)
    ss = sub.add_parser("self-scan", help="scan a working tree (default: this repo) for secrets")
    ss.add_argument("path", nargs="?", default=str(config_mod.ROOT))
    ss.set_defaults(fn=cmd_self_scan)
    a = p.parse_args(argv)
    setup_logging(a.log_level)
    try:
        return a.fn(a)
    except (GatewayError, GitHubError) as e:
        print(f"error: {scrub(str(e))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
