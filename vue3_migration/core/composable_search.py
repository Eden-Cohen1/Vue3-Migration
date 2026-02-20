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


def search_for_composable(mixin_stem: str, composable_dirs: list[Path]) -> list[Path]:
    """Search for composable files matching a mixin name.

    Phase 1: Exact stem match against generated candidate names (case-insensitive).
    Phase 2: Fuzzy -- any 'use' file whose name contains the mixin's core word.
    """
    candidates = generate_candidates(mixin_stem)
    matches = []

    # Phase 1: Exact name match (case-insensitive)
    for comp_dir in composable_dirs:
        for dirpath, _, filenames in os.walk(comp_dir):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.suffix not in (".js", ".ts"):
                    continue
                if any(filepath.stem.lower() == c.lower() for c in candidates):
                    matches.append(filepath)

    if matches:
        return list(dict.fromkeys(matches))

    # Phase 2: Fuzzy fallback -- "use" prefix + core word substring
    core_word = re.sub(r"[_-]?[Mm]ixin$", "", mixin_stem).lower()
    if not core_word:
        return []

    for comp_dir in composable_dirs:
        for dirpath, _, filenames in os.walk(comp_dir):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.suffix not in (".js", ".ts"):
                    continue
                if filepath.stem.lower().startswith("use") and core_word in filepath.stem.lower():
                    matches.append(filepath)

    return list(dict.fromkeys(matches))


def collect_composable_stems(composable_dirs: list[Path]) -> set[str]:
    """Collect all composable file stems (e.g. 'useSelection') from all dirs.

    Used for quick existence checks during scanning.
    """
    stems: set[str] = set()
    for comp_dir in composable_dirs:
        for dirpath, _, filenames in os.walk(comp_dir):
            for fn in filenames:
                fp = Path(dirpath) / fn
                if fp.suffix in (".js", ".ts") and fp.stem.startswith("use"):
                    stems.add(fp.stem.lower())
    return stems


def mixin_has_composable(mixin_stem: str, composable_stems: set[str]) -> bool:
    """Check if a matching composable likely exists for a mixin name."""
    core = re.sub(r"[_-]?[Mm]ixin$", "", mixin_stem)
    if not core:
        return False

    names_to_check = [core]
    without_common = re.sub(r"[_-]?[Cc]ommon$", "", core)
    if without_common != core:
        names_to_check.append(without_common)

    for name in names_to_check:
        candidate = "use" + name[0].upper() + name[1:]
        if candidate.lower() in composable_stems:
            return True
        if ("use" + name.capitalize()).lower() in composable_stems:
            return True

    return False
