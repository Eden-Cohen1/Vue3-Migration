"""Unified diff generation and colored terminal display."""
import difflib
from pathlib import Path

from ..models import FileChange
from .terminal import bold, cyan, dim, green, red


def build_unified_diff(original: str, modified: str, path: str) -> str:
    """Generate a unified diff string between original and modified content.

    Returns an empty string if there are no changes.

    Args:
        original: The original file content.
        modified: The modified file content.
        path: File path used as the diff header label.

    Returns:
        A unified diff string, or "" if original == modified.
    """
    if original == modified:
        return ""
    lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    ))
    return "\n".join(lines)


def print_diff_summary(
    changes: list[FileChange],
    project_root: Path | None = None,
) -> None:
    """Print a colored unified diff for all planned FileChange objects.

    Files with no changes are silently skipped.
    Added lines (+) are green, removed lines (-) are red,
    hunk headers (@@) are cyan, everything else is dim.

    Args:
        changes: List of FileChange objects.
        project_root: If provided, paths are shown relative to this root.
    """
    any_printed = False
    for change in changes:
        if not change.has_changes:
            continue
        rel = (
            str(change.file_path.relative_to(project_root))
            if project_root
            else str(change.file_path)
        )
        diff = build_unified_diff(change.original_content, change.new_content, rel)
        if not diff:
            continue
        print(f"\n{bold(rel)}")
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                print(green(line))
            elif line.startswith("-") and not line.startswith("---"):
                print(red(line))
            elif line.startswith("@@"):
                print(cyan(line))
            else:
                print(dim(line))
        any_printed = True
    if not any_printed:
        print(dim("  (no changes to display)"))
