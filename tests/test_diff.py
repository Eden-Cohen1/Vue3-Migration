"""Tests for vue3_migration.reporting.diff."""
from vue3_migration.reporting.diff import build_unified_diff

def test_detects_change():
    diff = build_unified_diff("hello\n", "hello world\n", "test.js")
    assert "-hello" in diff
    assert "+hello world" in diff

def test_no_change_returns_empty_string():
    assert build_unified_diff("same\n", "same\n", "test.js") == ""

def test_includes_path_in_header():
    diff = build_unified_diff("a\n", "b\n", "src/foo.vue")
    assert "src/foo.vue" in diff

def test_multiline_diff():
    orig = "line1\nline2\nline3\n"
    mod  = "line1\nLINE2\nline3\n"
    diff = build_unified_diff(orig, mod, "x.js")
    assert "-line2" in diff
    assert "+LINE2" in diff
