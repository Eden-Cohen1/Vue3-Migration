"""
Composable search — find composable files matching mixin names.

Generates candidate composable names from mixin filenames, searches
Composables directories with exact then fuzzy matching.
"""

import os
import re
from pathlib import Path


def generate_candidates(mixin_stem: str) -> list[str]:
    """Generate expected composable names from a mixin filename.

    selectionMixin         -> [useSelection]
    LPiMixin               -> [useLPi, useLpi]
    PropertiesCommonMixin  -> [usePropertiesCommon, useProperties]
    mapHelpers             -> [useMapHelpers, useMaphelpers]
    """
    # Strip "Mixin" suffix (with optional _ or - prefix)
    core_name = re.sub(r"[_-]?[Mm]ixin$", "", mixin_stem)
    if not core_name:
        return []

    # Primary: preserve original casing after "use"
    primary = "use" + core_name[0].upper() + core_name[1:]
    # Secondary: capitalize-style for edge cases
    secondary = "use" + core_name.capitalize()

    candidates = [primary, secondary]

    # Also try stripping "Common" if present
    without_common = re.sub(r"[_-]?[Cc]ommon$", "", core_name)
    if without_common and without_common != core_name:
        candidates.append("use" + without_common[0].upper() + without_common[1:])
        candidates.append("use" + without_common.capitalize())

    return list(dict.fromkeys(candidates))


def find_composable_dirs(project_root: Path) -> list[Path]:
    """Find all directories named 'Composables' (case-insensitive) in the project."""
    found = []
    for dirpath, dirnames, _ in os.walk(project_root):
        # Skip node_modules, dist, .git
        rel = Path(dirpath).relative_to(project_root)
        if any(part in {"node_modules", "dist", ".git", "__pycache__"} for part in rel.parts):
            continue
        for dirname in dirnames:
            if dirname.lower() == "composables":
                found.append(Path(dirpath) / dirname)
    return found


_SKIP_DIRS = {"node_modules", "dist", ".git", "__pycache__"}


def find_all_composable_files(project_root: Path) -> list[Path]:
    """Find every .js/.ts file whose stem starts with 'use' anywhere in the project.

    Skips node_modules, dist, .git, __pycache__.
    """
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        rel = Path(dirpath).relative_to(project_root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            dirnames[:] = []
            continue
        # Prune skipped dirs in-place so os.walk won't descend into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            fp = Path(dirpath) / fn
            if fp.suffix in (".js", ".ts") and fp.stem.lower().startswith("use"):
                files.append(fp)
    return files


def search_for_composable(
    mixin_stem: str,
    composable_dirs: list[Path],
    project_root: "Path | None" = None,
) -> list[Path]:
    """Search for composable files matching a mixin name.

    Phase 1: Exact stem match against generated candidate names (case-insensitive).
    Phase 2: Fuzzy -- any 'use' file whose name contains the mixin's core word.

    If no matches found in composable_dirs and project_root is provided,
    repeats both phases across all use*.js/ts files found project-wide.
    """
    candidates = generate_candidates(mixin_stem)
    matches = []

    def _search_files(files: list[Path]) -> list[Path]:
        found = []
        # Phase 1: exact
        for fp in files:
            if any(fp.stem.lower() == c.lower() for c in candidates):
                found.append(fp)
        if found:
            return list(dict.fromkeys(found))
        # Phase 2: fuzzy
        core_word = re.sub(r"[_-]?[Mm]ixin$", "", mixin_stem).lower()
        if not core_word:
            return []
        for fp in files:
            if fp.stem.lower().startswith("use") and core_word in fp.stem.lower():
                found.append(fp)
        return list(dict.fromkeys(found))

    # Collect files from named composable directories
    dir_files: list[Path] = []
    for comp_dir in composable_dirs:
        for dirpath, _, filenames in os.walk(comp_dir):
            for filename in filenames:
                fp = Path(dirpath) / filename
                if fp.suffix in (".js", ".ts"):
                    dir_files.append(fp)

    matches = _search_files(dir_files)
    if matches:
        return matches

    # Fallback: project-wide search
    if project_root is not None:
        all_files = find_all_composable_files(project_root)
        # Exclude files already covered by composable_dirs to avoid duplicates
        dir_file_set = set(dir_files)
        extra_files = [f for f in all_files if f not in dir_file_set]
        matches = _search_files(extra_files)

    return matches


def collect_composable_stems(
    composable_dirs: list[Path],
    project_root: "Path | None" = None,
) -> set[str]:
    """Collect all composable file stems (e.g. 'useSelection') from all dirs.

    Used for quick existence checks during scanning.

    If composable_dirs yields no stems and project_root is provided,
    falls back to a project-wide search via find_all_composable_files.
    """
    stems: set[str] = set()
    for comp_dir in composable_dirs:
        for dirpath, _, filenames in os.walk(comp_dir):
            for fn in filenames:
                fp = Path(dirpath) / fn
                if fp.suffix in (".js", ".ts") and fp.stem.lower().startswith("use"):
                    stems.add(fp.stem.lower())

    if not stems and project_root is not None:
        for fp in find_all_composable_files(project_root):
            stems.add(fp.stem.lower())

    return stems


def mixin_has_composable(mixin_stem: str, composable_stems: set[str]) -> bool:
    """Check if a matching composable likely exists for a mixin name.

    Uses the same two-phase strategy as search_for_composable:
    Phase 1 — exact candidate match (useFilter, useFilter).
    Phase 2 — fuzzy: any composable stem starting with 'use' that contains
               the core word as a substring (e.g. useAdvancedFilter for filterMixin).
    """
    core = re.sub(r"[_-]?[Mm]ixin$", "", mixin_stem)
    if not core:
        return False

    names_to_check = [core]
    without_common = re.sub(r"[_-]?[Cc]ommon$", "", core)
    if without_common != core:
        names_to_check.append(without_common)

    # Phase 1: exact candidate match
    for name in names_to_check:
        candidate = "use" + name[0].upper() + name[1:]
        if candidate.lower() in composable_stems:
            return True
        if ("use" + name.capitalize()).lower() in composable_stems:
            return True

    # Phase 2: fuzzy — core word as substring of any use* composable
    core_lower = core.lower()
    for stem in composable_stems:
        if stem.startswith("use") and core_lower in stem:
            return True

    return False
