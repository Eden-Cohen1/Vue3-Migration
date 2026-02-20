"""
Import path resolution — resolve JS/TS import paths to actual files on disk.

Handles relative paths, @/ alias (mapped to src/), and @ prefix without slash.
"""

import re
from pathlib import Path
from typing import Optional

FILE_EXTENSIONS = (".js", ".ts")


def find_src_directory(starting_dir: Path) -> Optional[Path]:
    """Walk upward from starting_dir to find the nearest directory containing 'src/'."""
    search = starting_dir.resolve()
    while search != search.parent:
        candidate = search / "src"
        if candidate.is_dir():
            return candidate
        search = search.parent
    return None


def try_resolve_with_extensions(base_path: Path) -> Optional[Path]:
    """Try to resolve a path as-is, then with .js and .ts extensions."""
    for candidate in [base_path, base_path.with_suffix(".js"), base_path.with_suffix(".ts")]:
        if candidate.is_file():
            return candidate
    return None


def resolve_import_path(import_path: str, component_path: Path) -> Optional[Path]:
    """Resolve an import path to an actual file on disk.

    Handles three styles:
      - Relative:     '../mixins/foo'
      - @/ alias:     '@/components/foo'    (@ = src/)
      - @ prefix:     '@components/foo'     (@ = src/)
    """
    component_dir = component_path.parent

    # --- Case 1: Relative path (starts with . or /) ---
    if import_path.startswith(".") or import_path.startswith("/"):
        base = (component_dir / import_path).resolve()
        return try_resolve_with_extensions(base)

    # --- Case 2 & 3: @ alias (@/ or @ without /) ---
    if import_path.startswith("@"):
        src_dir = find_src_directory(component_dir)
        if not src_dir:
            return None

        # "@/components/foo" -> strip "@/" -> "components/foo"
        # "@components/foo"  -> strip "@"  -> "components/foo"
        if import_path.startswith("@/"):
            relative_part = import_path[2:]
        else:
            relative_part = import_path[1:]

        base = (src_dir / relative_part).resolve()
        return try_resolve_with_extensions(base)

    # --- Fallback: treat as relative ---
    base = (component_dir / import_path).resolve()
    return try_resolve_with_extensions(base)


def compute_import_path(composable_path: Path, project_root: Path) -> str:
    """Build the import path for a composable, using @/ alias when under src/.

    Resolves the actual file path relative to the project root and replaces
    the src/ prefix with @/.
    """
    try:
        relative = composable_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        relative = composable_path

    normalized = str(relative).replace("\\", "/")
    normalized = re.sub(r"\.(js|ts)$", "", normalized)

    # Replace everything up to and including "src/" with "@/"
    src_idx = normalized.find("src/")
    if src_idx != -1:
        return "@/" + normalized[src_idx + 4:]

    return normalized


def resolve_mixin_stem(import_path: str) -> str:
    """Extract the mixin filename stem from an import path.

    '../mixins/selectionMixin' -> 'selectionMixin'
    '@/mixins/LPiMixin.js'    -> 'LPiMixin'
    """
    basename = import_path.rsplit("/", 1)[-1]
    return re.sub(r"\.(js|ts)$", "", basename)
