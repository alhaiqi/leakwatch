import json
import logging

import fakes
from leakwatch.scanner.detector import scan_patch, scan_unified, scan_text


def test_all_true_positives_detected(positive):
    text, values, expected = positive
    res = scan_unified(text)
    got = {(f.file, f.line, f.secret_type) for f in res.findings}
    want = {(file, line, kind) for file, line, kind in expected.values()}
    assert got == want, f"missing={want - got} extra={got - want}"


def test_zero_false_positives_on_placeholders(placeholders):
    res = scan_unified(placeholders)
    assert res.findings == [], [(f.file, f.line, f.secret_type) for f in res.findings]
    assert res.dropped, "placeholder candidates should be recorded as dropped with a reason"


def test_raw_value_never_in_any_output(positive, caplog):
    text, values, _ = positive
    caplog.set_level(logging.DEBUG)
    res = scan_unified(text)
    blobs = [repr(res), str(res)]
    for f in res.findings:
        blobs += [repr(f), str(f), json.dumps(f.to_dict()), f.masked, "\n".join(f.context)]
    blob = "\n".join(blobs) + caplog.text
    for name, v in values.items():
        if name == "FAKE_PEM_HEADER":
            continue  # the PEM header is a public constant; the key BODY is the secret (see test_pem_*)
        assert v not in blob, name
        if name.endswith("_URL"):
            pw = v.split("://", 1)[1].split("@")[0].split(":", 1)[1]
            assert pw not in blob, name


def test_context_is_masked_and_short(positive):
    text, values, _ = positive
    f = next(f for f in scan_unified(text).findings if f.secret_type == "aws_access_key_id")
    assert 1 <= len(f.context) <= 3
    assert any("AWS_ACCESS_KEY_ID" in c and f.masked in c for c in f.context)


def test_fingerprint_stable_and_repo_scoped():
    v = fakes.aws_key()
    a = scan_patch("a.py", f"@@ -0,0 +1 @@\n+K='{v}'\n").findings[0]
    b = scan_patch("a.py", f"@@ -0,0 +5 @@\n+X = \"{v}\"\n").findings[0]
    assert a.fingerprint("o/r") == b.fingerprint("o/r")
    assert a.fingerprint("o/r") != a.fingerprint("o/other")
    assert v not in a.fingerprint("o/r") and len(a.fingerprint("o/r")) == 64


def test_test_paths_lower_confidence_not_dropped():
    v = fakes.aws_key()
    prod = scan_patch("app/a.py", f"@@ -0,0 +1 @@\n+K='{v}'\n").findings[0]
    test = scan_patch("tests/a.py", f"@@ -0,0 +1 @@\n+K='{v}'\n").findings[0]
    assert test.confidence < prod.confidence and prod.confidence >= 0.8


def test_only_added_lines_scanned():
    v = fakes.aws_key()
    assert scan_patch("a.py", f"@@ -1 +1 @@\n-K='{v}'\n+K=os.environ['K']\n").findings == []
    assert scan_patch("a.py", f"@@ -1 +1 @@\n K='{v}'\n+x=1\n").findings == []


def test_skipped_files_reported():
    res = scan_patch("package-lock.json", f"@@ -0,0 +1 @@\n+{fakes.aws_key()}\n")
    assert res.findings == [] and res.skipped == [("package-lock.json", "lockfile")]


def test_same_secret_twice_in_one_file_reported_once():
    v = fakes.github_pat()
    res = scan_patch("a.py", f"@@ -0,0 +1,2 @@\n+A='{v}'\n+B='{v}'\n")
    assert len(res.findings) == 1


def test_scan_text_whole_file():
    v = fakes.stripe_live()
    res = scan_text("x/settings.py", f"import os\nKEY = '{v}'\n")
    assert [(f.line, f.secret_type) for f in res.findings] == [(2, "stripe_secret_key")]


def test_pem_finding_masked_without_body():
    res = scan_patch("k", f"@@ -0,0 +1,2 @@\n+{fakes.pem_header()}\n+MIIEowIBAAKCAQEAxyz\n")
    f = res.findings[0]
    assert "MIIEowIBAAKCAQEAxyz" not in f.masked + "".join(f.context)
