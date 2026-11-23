from leakwatch.scanner.diff import added_lines, parse_patch, parse_unified, should_skip

PATCH = """@@ -1,3 +1,4 @@
 line1
-old
+new2
+new3
 line4
@@ -10,2 +11,3 @@ def f():
 ctx11
+added12
\\ No newline at end of file
"""


def test_parse_patch_tracks_new_line_numbers():
    lines = parse_patch(PATCH)
    assert [(l.line_no, l.text, l.added) for l in lines] == [
        (1, "line1", False), (2, "new2", True), (3, "new3", True), (4, "line4", False),
        (11, "ctx11", False), (12, "added12", True),
    ]


def test_added_lines_only():
    assert [(l.line_no, l.text) for l in added_lines(parse_patch(PATCH))] == [
        (2, "new2"), (3, "new3"), (12, "added12")]


def test_plus_plus_content_line_is_added_not_header():
    # a removed "--x" and added "++y" content line inside a hunk must not be taken as headers
    p = "@@ -1 +1 @@\n---x\n+++y\n"
    assert [(l.line_no, l.text) for l in added_lines(parse_patch(p))] == [(1, "++y")]


def test_parse_unified_multi_file(positive):
    text, _, _ = positive
    files = parse_unified(text)
    assert set(files) == {"app/config.py", "deploy/.env.production", "keys/deploy_key", "src/settings.js"}
    assert [l.line_no for l in added_lines(files["deploy/.env.production"])] == list(range(1, 10))


def test_parse_unified_skips_deleted_file():
    d = "diff --git a/x b/x\ndeleted file mode 100644\n--- a/x\n+++ /dev/null\n@@ -1 +0,0 @@\n-gone\n"
    assert parse_unified(d) == {}


def test_empty_and_none():
    assert parse_patch("") == [] and parse_patch(None) == []


def test_should_skip():
    assert should_skip("package-lock.json") == "lockfile"
    assert should_skip("sub/yarn.lock") == "lockfile"
    assert should_skip("vendor/lib/a.go") == "vendored"
    assert should_skip("web/node_modules/x/index.js") == "vendored"
    assert should_skip("img/logo.png") == "binary"
    assert should_skip("a.py", patch=None) == "binary"
    assert should_skip("a.py", patch="x" * (1024 * 1024 + 1)) == "too_large"
    assert should_skip("app/config.py", patch="@@") is None
