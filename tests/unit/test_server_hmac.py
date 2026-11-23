import hashlib
import hmac
import json
import time

import pytest
from starlette.testclient import TestClient

from leakwatch.config import Config
from leakwatch.server import create_app, verify_signature

SECRET = "s3cr3t-for-tests-only"


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class FakePipeline:
    def __init__(self):
        self.calls = []

    def process_commit(self, repo, sha, ref=None, source=""):
        self.calls.append((repo, sha, ref, source))


@pytest.fixture
def client(tmp_path):
    cfg = Config(repos=["o/r"], data_dir=tmp_path, heartbeat_seconds=3600)
    pipe = FakePipeline()
    app = create_app(cfg, pipe, SECRET)
    with TestClient(app) as c:
        c.pipe = pipe
        yield c


def push(repo="o/r", shas=("a" * 40,), ref="refs/heads/main", **extra):
    head = shas[-1] if shas else "0" * 40
    p = {"ref": ref, "after": head, "repository": {"full_name": repo},
         "commits": [{"id": s} for s in shas], "head_commit": {"id": head}}
    p.update(extra)
    return json.dumps(p).encode()


def post(c, body, event="push", sig=None):
    return c.post("/github/webhook", content=body, headers={
        "X-GitHub-Event": event, "X-Hub-Signature-256": sig if sig is not None else sign(body),
        "X-GitHub-Delivery": "d1", "Content-Type": "application/json"})


def wait_calls(c, n, timeout=3):
    end = time.time() + timeout
    while time.time() < end and len(c.pipe.calls) < n:
        time.sleep(0.02)
    return c.pipe.calls


def test_verify_signature_unit():
    b = b'{"x":1}'
    assert verify_signature(SECRET, b, sign(b))
    assert not verify_signature(SECRET, b, sign(b, "other"))
    assert not verify_signature(SECRET, b, None)
    assert not verify_signature(SECRET, b, "sha1=abc")
    assert not verify_signature(SECRET, b + b" ", sign(b))


def test_bad_signature_401(client):
    r = post(client, push(), sig="sha256=" + "0" * 64)
    assert r.status_code == 401 and client.pipe.calls == []


def test_missing_signature_401(client):
    r = client.post("/github/webhook", content=push(), headers={"X-GitHub-Event": "push"})
    assert r.status_code == 401


def test_valid_push_is_202_fast_and_processed_async(client):
    t = time.time()
    r = post(client, push(shas=("a" * 40, "b" * 40)))
    assert r.status_code == 202 and time.time() - t < 1.0
    assert r.json()["queued"] == 2
    calls = wait_calls(client, 2)
    assert [(c[1], c[2], c[3]) for c in calls] == [("a" * 40, "refs/heads/main", "webhook"),
                                                    ("b" * 40, "refs/heads/main", "webhook")]


def test_non_push_event_ignored(client):
    r = post(client, b'{"zen":"hi"}', event="issues")
    assert r.status_code == 202 and r.json()["status"] == "ignored"
    assert client.pipe.calls == []


def test_ping_ok(client):
    r = post(client, b'{"zen":"hi","hook_id":1}', event="ping")
    assert r.status_code == 200 and r.json()["status"] == "pong"


def test_unwatched_repo_ignored(client):
    r = post(client, push(repo="someone/else"))
    assert r.status_code == 202 and r.json()["status"] == "ignored"


def test_branch_delete_ignored(client):
    r = post(client, push(shas=(), deleted=True, after="0" * 40, head_commit=None))
    assert r.json()["status"] == "ignored"


def test_bad_json_400(client):
    body = b"not json"
    assert post(client, body).status_code == 400


def test_oversize_413(client):
    body = b"x" * (5 * 1024 * 1024 + 1)
    assert post(client, body).status_code == 413


def test_healthz_and_heartbeat(client, tmp_path):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert (tmp_path / "heartbeat.log").exists()
