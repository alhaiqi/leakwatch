import fakes
from leakwatch.scanner.detector import scan_patch
from leakwatch.store import Store


def test_claim_is_atomic_and_release_only_unreported(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.claim("fp1", "o/r", "a.py", "aws", "sha") is True
    assert s.claim("fp1", "o/r", "a.py", "aws", "sha") is False
    s.release("fp1")
    assert s.known("fp1") is None
    s.claim("fp1", "o/r", "a.py", "aws", "sha"); s.set_issue("fp1", "https://x/1"); s.release("fp1")
    assert s.known("fp1") == "https://x/1"


def test_db_never_contains_secret(tmp_path):
    v = fakes.aws_key()
    f = scan_patch("a.py", f"@@ -0,0 +1 @@\n+K='{v}'\n").findings[0]
    s = Store(tmp_path / "t.db")
    s.claim(f.fingerprint("o/r"), "o/r", f.file, f.secret_type, "sha")
    s.log_run("cli", "o/r", "sha", "ok", repr(f))
    s.mark_processed("o/r", "sha", 1, 1)
    assert s.is_processed("o/r", "sha")
    assert v.encode() not in (tmp_path / "t.db").read_bytes()
    assert (tmp_path / "t.db").stat().st_mode & 0o077 == 0
