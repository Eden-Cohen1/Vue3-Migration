"""Centralized file reading with explicit UTF-8 encoding."""
from pathlib import Path


def read_source(path: Path) -> str:
    """Read a source file as UTF-8, normalizing line endings to LF."""
    return path.read_text(encoding="utf-8", errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
