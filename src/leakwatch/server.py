"""Webhook server: HMAC-verified GitHub push events → async queue → pipeline. Replies 202 at once."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import time

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from . import __version__
from .config import Config

log = logging.getLogger("leakwatch.server")
MAX_BODY = 5 * 1024 * 1024
BOOT_ID = open("/proc/sys/kernel/random/boot_id").read().strip() if os.path.exists("/proc/sys/kernel/random/boot_id") else "unknown"


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def create_app(cfg: Config, pipeline, secret: str, poll: int = 0, gh=None, store=None) -> Starlette:
    state = {"queue": None, "started": time.time(), "processed": 0, "last_error": None}

    async def worker():
        q: asyncio.Queue = state["queue"]
        while True:
            repo, sha, ref, source = await q.get()
            try:
                await asyncio.to_thread(pipeline.process_commit, repo, sha, ref, source)
                state["processed"] += 1
            except Exception as e:  # keep the worker alive no matter what
                state["last_error"] = f"{type(e).__name__}"
                log.exception("processing %s@%s failed", repo, sha[:10])
            finally:
                q.task_done()

    async def heartbeat():
        path = cfg.data_dir / "heartbeat.log"
        while True:
            with open(path, "a") as f:
                f.write(f"{time.time():.0f} {time.monotonic():.0f} {os.getpid()} {BOOT_ID}\n")
            await asyncio.sleep(cfg.heartbeat_seconds)

    async def poller():
        """Fallback mode: poll each watched repo's default branch for unprocessed commits."""
        while True:
            for repo in cfg.repos:
                try:
                    commits = await asyncio.to_thread(gh.commits, repo, 10)
                    for c in reversed(commits):
                        if not store.is_processed(repo, c["sha"]):
                            await state["queue"].put((repo, c["sha"], None, "poll"))
                    print(f"poll heartbeat {time.strftime('%H:%M:%S')} {repo} ok", flush=True)
                except Exception as e:
                    log.warning("poll %s failed: %s", repo, type(e).__name__)
            await asyncio.sleep(poll)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        state["queue"] = asyncio.Queue(maxsize=1000)
        tasks = [asyncio.create_task(worker()), asyncio.create_task(heartbeat())]
        if poll:
            tasks.append(asyncio.create_task(poller()))
        log.info("LeakWatch %s up; watching %s; mode=%s", __version__, ", ".join(cfg.repos),
                 f"poll/{poll}s" if poll else "webhook")
        yield
        for t in tasks:
            t.cancel()

    async def index(request: Request):
        return PlainTextResponse("LeakWatch is watching. POST GitHub push webhooks to /github/webhook.\n")

    async def healthz(request: Request):
        return JSONResponse({"status": "ok", "version": __version__, "pid": os.getpid(), "boot": BOOT_ID[:8],
                             "uptime_s": round(time.time() - state["started"]),
                             "queued": state["queue"].qsize() if state["queue"] else 0,
                             "processed": state["processed"], "last_error": state["last_error"]})

    async def webhook(request: Request):
        if int(request.headers.get("content-length") or 0) > MAX_BODY:
            return JSONResponse({"error": "too large"}, 413)
        body = await request.body()
        if len(body) > MAX_BODY:
            return JSONResponse({"error": "too large"}, 413)
        if not verify_signature(secret, body, request.headers.get("x-hub-signature-256")):
            log.warning("rejected webhook: bad signature (delivery %s)", request.headers.get("x-github-delivery"))
            return JSONResponse({"error": "invalid signature"}, 401)
        event = request.headers.get("x-github-event", "")
        if event == "ping":
            return JSONResponse({"status": "pong"}, 200)
        if event != "push":
            return JSONResponse({"status": "ignored", "reason": f"event {event!r}"}, 202)
        try:
            p = json.loads(body)
            repo = p["repository"]["full_name"]
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "bad payload"}, 400)
        if not cfg.is_watched(repo):
            return JSONResponse({"status": "ignored", "reason": "repo not watched"}, 202)
        if p.get("deleted") or not p.get("commits") and not p.get("head_commit"):
            return JSONResponse({"status": "ignored", "reason": "no commits"}, 202)
        shas = [c["id"] for c in p.get("commits") or []] or [p["head_commit"]["id"]]
        ref = p.get("ref")
        for sha in shas:
            state["queue"].put_nowait((repo, sha, ref, "webhook"))
        log.info("queued %d commit(s) from %s %s (delivery %s)", len(shas), repo, ref,
                 request.headers.get("x-github-delivery"))
        return JSONResponse({"status": "queued", "queued": len(shas)}, 202)

    return Starlette(routes=[Route("/", index), Route("/healthz", healthz),
                             Route("/github/webhook", webhook, methods=["POST"])], lifespan=lifespan)


def run(ctx, secret: str, poll: int = 0) -> None:
    import uvicorn
    app = create_app(ctx.cfg, ctx.pipeline, secret, poll=poll, gh=ctx.gh, store=ctx.store)
    uvicorn.run(app, host="0.0.0.0", port=ctx.cfg.port, log_level="info", access_log=True)
