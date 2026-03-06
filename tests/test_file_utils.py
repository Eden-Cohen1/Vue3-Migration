import pytest
from pathlib import Path
from vue3_migration.core.file_utils import read_source


def test_read_source_utf8(tmp_path):
    """read_source decodes UTF-8 files correctly, including Unicode box chars."""
    content = "// \u250c\u2500 MIGRATION WARNINGS\n// \u2502 \u274c message\n// \u2514\u2500\u2500\u2500\n"
    p = tmp_path / "test.js"
    p.write_text(content, encoding="utf-8")
    result = read_source(p)
    assert "\u250c" in result  # ┌
    assert "\u274c" in result  # ❌
    assert "\r" not in result  # CRLF normalized


def test_read_source_normalizes_crlf(tmp_path):
    """read_source normalizes CRLF to LF."""
    p = tmp_path / "test.js"
    p.write_bytes(b"line1\r\nline2\r\n")
    result = read_source(p)
    assert result == "line1\nline2\n"
