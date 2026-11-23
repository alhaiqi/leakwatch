"""SQLite state: fingerprint hashes (never secrets), processed SHAs, run log."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS fingerprints (
  fp TEXT PRIMARY KEY, repo TEXT, file TEXT, secret_type TEXT, commit_sha TEXT,
  issue_url TEXT, first_seen REAL);
CREATE TABLE IF NOT EXISTS processed (
  repo TEXT, sha TEXT, processed_at REAL, findings INTEGER, reported INTEGER,
  PRIMARY KEY (repo, sha));
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, repo TEXT, sha TEXT,
  status TEXT, detail TEXT);
"""


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        if self.path != ":memory:":
            Path(self.path).chmod(0o600)

    # Dedupe is claim-then-report: claim atomically, release if reporting fails.
    def claim(self, fp: str, repo: str, file: str, secret_type: str, sha: str) -> bool:
        with self._lock:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO fingerprints(fp, repo, file, secret_type, commit_sha, first_seen)"
                " VALUES (?,?,?,?,?,?)", (fp, repo, file, secret_type, sha, time.time()))
            return cur.rowcount == 1

    def set_issue(self, fp: str, url: str) -> None:
        with self._lock:
            self.db.execute("UPDATE fingerprints SET issue_url=? WHERE fp=?", (url, fp))

    def release(self, fp: str) -> None:
        with self._lock:
            self.db.execute("DELETE FROM fingerprints WHERE fp=? AND issue_url IS NULL", (fp,))

    def known(self, fp: str) -> str | None:
        row = self.db.execute("SELECT COALESCE(issue_url, '') FROM fingerprints WHERE fp=?", (fp,)).fetchone()
        return None if row is None else row[0]

    def mark_processed(self, repo: str, sha: str, findings: int, reported: int) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO processed VALUES (?,?,?,?,?)",
                            (repo, sha, time.time(), findings, reported))

    def is_processed(self, repo: str, sha: str) -> bool:
        return self.db.execute("SELECT 1 FROM processed WHERE repo=? AND sha=?", (repo, sha)).fetchone() is not None

    def log_run(self, kind: str, repo: str, sha: str, status: str, detail: str = "") -> None:
        with self._lock:
            self.db.execute("INSERT INTO runs(ts, kind, repo, sha, status, detail) VALUES (?,?,?,?,?,?)",
                            (time.time(), kind, repo, sha, status, detail[:2000]))

    def recent_runs(self, n: int = 10) -> list[tuple]:
        return self.db.execute("SELECT ts, kind, repo, sha, status, detail FROM runs ORDER BY id DESC LIMIT ?",
                               (n,)).fetchall()
