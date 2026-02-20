"""
Mixin-centric audit and migration workflow.

Scans a Vue codebase to audit a mixin's usage, compares against a composable,
and optionally injects the composable into all importing components.

BUG FIX: Unlike the original mixin_audit.py, this workflow correctly detects
component overrides before injection — members that the component defines
itself are excluded from composable destructuring.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

from ..core.component_analyzer import extract_own_members, find_used_members
from ..core.composable_analyzer import (
    extract_all_identifiers,
    extract_function_name,
)
from ..core.composable_search import (
    find_composable_dirs,
    generate_candidates,
    search_for_composable,
)
from ..core.file_resolver import compute_import_path
from ..core.mixin_analyzer import extract_lifecycle_hooks, extract_mixin_members
from ..models import FileChange, MigrationConfig
from ..reporting.markdown import build_audit_report
from ..reporting.terminal import bold, cyan, dim, green, red, red_bold, yellow
from ..transform.injector import (
    add_composable_import,
    find_mixin_import_name,
    inject_setup,
    remove_import_line,
    remove_mixin_from_array,
)

FILE_EXTENSIONS = {".vue", ".js", ".ts"}


def find_files_importing_mixin(
    project_root: Path,
    mixin_path: Path,
    skip_dirs: set[str] | None = None,
) -> list[Path]:
    """Find all files that import a given mixin."""
    if skip_dirs is None:
        skip_dirs = {"node_modules", "dist", ".git", "__pycache__"}

    mixin_filename = mixin_path.stem
    importing_files = []
    for dirpath, _, filenames in os.walk(project_root):
        rel = Path(dirpath).relative_to(project_root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path.suffix not in FILE_EXTENSIONS:
                continue
            if file_path.resolve() == mixin_path.resolve():
                continue
            try:
                content = file_path.read_text(errors="ignore")
            except OSError:
                continue
            import_pattern = (
                rf"""(?:import|require)\s*.*?['"\/]"""
                rf"""{re.escape(mixin_filename)}(?:\.(?:js|ts))?['"]"""
            )
            if re.search(import_pattern, content):
                importing_files.append(file_path)
    return importing_files


def find_used_members_in_file(file_path: Path, member_names: list[str]) -> list[str]:
    """Find which mixin members are referenced in a file."""
    file_content = file_path.read_text(errors="ignore")
    return find_used_members(file_content, member_names)


def plan_injection_for_file(
    file_path: Path,
    mixin_path: Path,
    import_path: str,
    composable_fn_name: str,
    used_members: list[str],
) -> FileChange:
    """Plan composable injection for a single file.

    BUG FIX: This function now detects component overrides. Members that the
    component defines itself in data/computed/methods/watch are excluded from
    the composable destructuring.
    """
    file_content = file_path.read_text(errors="ignore")
    original_content = file_content
    changes: list[str] = []

    mixin_stem = mixin_path.stem
    mixin_local_name = find_mixin_import_name(file_content, mixin_stem)

    # Detect component overrides — members the component defines itself
    component_own = extract_own_members(file_content)
    injectable_members = [m for m in used_members if m not in component_own]
    overridden = [m for m in used_members if m in component_own]

    if overridden:
        changes.append(f"Skipped {len(overridden)} overridden member(s): {', '.join(overridden)}")

    # Step 1: Remove mixin import
    new_content = remove_import_line(file_content, mixin_stem)
    if new_content != file_content:
        changes.append("Removed mixin import")
        file_content = new_content

    # Step 2: Add composable import (only if there are injectable members)
    if injectable_members:
        new_content = add_composable_import(file_content, composable_fn_name, import_path)
        if new_content != file_content:
            changes.append(f"Added import {{ {composable_fn_name} }}")
            file_content = new_content

    # Step 3: Remove mixin from mixins array
    if mixin_local_name:
        new_content = remove_mixin_from_array(file_content, mixin_local_name)
        if new_content != file_content:
            changes.append(f"Removed {mixin_local_name} from mixins array")
            file_content = new_content

    # Step 4: Inject setup() with injectable members only
    if injectable_members:
        new_content = inject_setup(file_content, [(composable_fn_name, injectable_members)])
        if new_content != file_content:
            had_setup = bool(re.search(r"\bsetup\s*\(", file_content))
            if had_setup:
                changes.append(f"Merged {{ {', '.join(injectable_members)} }} into existing setup()")
            else:
                changes.append(f"Created setup() with {{ {', '.join(injectable_members)} }}")
            file_content = new_content

    # Clean up excessive blank lines
    if file_content != original_content:
        file_content = re.sub(r"\n{3,}", "\n\n", file_content)

    return FileChange(
        file_path=file_path,
        original_content=original_content,
        new_content=file_content,
        changes=changes,
    )


def apply_changes(file_change: FileChange) -> None:
    """Write planned changes to disk."""
    if file_change.has_changes:
        file_change.file_path.write_text(file_change.new_content)


def prompt_and_inject(
    importing_files: list[Path],
    all_member_names: list[str],
    mixin_path: Path,
    composable_path_arg: Optional[str],
    project_root: Path,
):
    """Interactive prompt: ask user if they want to inject composable setup."""

    if not composable_path_arg:
        print("\nNo composable available. Skipping injection.")
        return

    composable_path = Path(composable_path_arg).resolve()
    if not composable_path.is_file():
        print(f"Composable file not found: {composable_path}")
        return

    # Extract composable function name
    composable_source = composable_path.read_text(errors="ignore")
    fn_name = extract_function_name(composable_source)

    if not fn_name:
        print("Could not detect composable function name.")
        fn_name = input("Enter the composable function name (e.g. useItems): ").strip()
        if not fn_name:
            return
    else:
        print(f"\nComposable function: {cyan(fn_name)}")

    # Compute import path
    import_path = compute_import_path(composable_path, project_root)
    print(f"Import path: {import_path}")

    # Check for missing members
    composable_identifiers = extract_all_identifiers(composable_source)
    missing_members = [m for m in all_member_names if m not in composable_identifiers]

    if missing_members:
        print(f"\n  {red_bold('WARNING')}: The following mixin members are "
              f"{red_bold('missing from the composable')}:")
        print(f"  {red_bold(', '.join(missing_members))}")
        print(f"  These members are defined in the mixin but not found in {cyan(fn_name)}.")
        print(f"  Components using these members may break after injection.")

    # Collect per-file usage
    files_with_usage = []
    for file_path in sorted(importing_files):
        used = find_used_members_in_file(file_path, all_member_names)
        if used:
            files_with_usage.append((file_path, used))

    files_to_inject = len(files_with_usage)
    files_to_skip = len(importing_files) - files_to_inject

    # Show injection summary
    print(f"\n{bold('Ready to inject')} {cyan(fn_name)} {bold('into')} "
          f"{cyan(str(files_to_inject))} {bold('file(s)')}")
    print(f"  This will, for each file:")
    print(f"    - Remove the {bold(mixin_path.stem)} import and mixins: [] entry")
    print(f"    - Add {cyan('import { ' + fn_name + ' }')} from '{import_path}'")
    print(f"    - Create or merge a {cyan('setup()')} function that destructures "
          f"the used members")
    print(f"    - {bold('Skip overridden members')} (members the component defines itself)")
    if files_to_skip:
        print(f"  {dim(f'{files_to_skip} file(s) with no detected member usage will be skipped.')}")
    if missing_members:
        print(f"  {red_bold('Note')}: {len(missing_members)} member(s) missing from "
              f"composable (see warning above).")

    answer = input(f"\n  Proceed? (y/n): ").strip().lower()
    if answer != "y":
        print("Skipped injection.")
        return

    # Inject into each file
    print(f"\nInjecting {fn_name} (from '{import_path}')...")
    for file_path in sorted(importing_files):
        rel_path = file_path.relative_to(project_root)
        used = find_used_members_in_file(file_path, all_member_names)

        if not used:
            print(f"  SKIP {rel_path} (no mixin members used)")
            continue

        file_change = plan_injection_for_file(
            file_path=file_path,
            mixin_path=mixin_path,
            import_path=import_path,
            composable_fn_name=fn_name,
            used_members=used,
        )

        if file_change.has_changes:
            apply_changes(file_change)
            print(f"  MODIFIED {rel_path}:")
            for change in file_change.changes:
                print(f"    - {change}")
        else:
            print(f"  UNCHANGED {rel_path}")

    print("\nDone. Review the changes and test your application.")


def run(mixin_arg: str, composable_arg: Optional[str] = None, config: MigrationConfig | None = None):
    """Main entry point for the mixin audit workflow."""
    if config is None:
        config = MigrationConfig()

    project_root = config.project_root
    mixin_path = Path(mixin_arg).resolve()
    if not mixin_path.is_file():
        sys.exit(f"Mixin not found: {mixin_path}")

    # --- Parse the mixin ---
    print(f"Parsing mixin: {mixin_path.name}...")
    mixin_source = mixin_path.read_text(errors="ignore")
    members = extract_mixin_members(mixin_source)
    lifecycle_hooks = extract_lifecycle_hooks(mixin_source)
    all_member_names = members["data"] + members["computed"] + members["methods"]
    print(f"  Found {len(all_member_names)} members and {len(lifecycle_hooks)} lifecycle hooks.")

    if not all_member_names and not lifecycle_hooks:
        sys.exit("No members or lifecycle hooks found in mixin. Check the file format.")

    # --- Find or resolve the composable ---
    composable_identifiers: list[str] = []
    composable_exists = False
    composable_path_resolved: Optional[str] = None

    if composable_arg:
        composable_path_resolved = composable_arg
    else:
        # Auto-search
        print(f"\nSearching for composable matching {green(mixin_path.stem)}...")
        candidates = generate_candidates(mixin_path.stem)
        print(f"  Looking for: {cyan(', '.join(candidates))}")
        comp_dirs = find_composable_dirs(project_root)
        matches = search_for_composable(mixin_path.stem, comp_dirs)

        if len(matches) == 1:
            found_path = matches[0]
            print(f"  Found: {green(str(found_path))}")
            answer = input(f"  Is this the correct composable? (y/n): ").strip().lower()
            if answer == "y":
                composable_path_resolved = str(found_path)
            else:
                user_path = input("  Enter the correct composable path "
                                  "(or press Enter to skip): ").strip()
                if user_path:
                    composable_path_resolved = user_path

        elif len(matches) > 1:
            print(f"  Multiple candidates found:")
            for i, fp in enumerate(matches, 1):
                print(f"    {i}. {fp}")
            choice = input(f"  Pick one (1-{len(matches)}), or 0 for none: ").strip()
            try:
                idx = int(choice)
                if 1 <= idx <= len(matches):
                    composable_path_resolved = str(matches[idx - 1])
            except ValueError:
                pass

            if not composable_path_resolved:
                user_path = input("  Enter composable path "
                                  "(or press Enter to skip): ").strip()
                if user_path:
                    composable_path_resolved = user_path
        else:
            print(f"  {yellow('No composable found automatically.')}")
            user_path = input("  Enter composable path "
                              "(or press Enter to skip): ").strip()
            if user_path:
                composable_path_resolved = user_path

    if composable_path_resolved:
        print(f"Parsing composable: {composable_path_resolved}...")
        composable_path = Path(composable_path_resolved).resolve()
        if composable_path.is_file():
            composable_exists = True
            composable_source = composable_path.read_text(errors="ignore")
            composable_identifiers = extract_all_identifiers(composable_source)
            print(f"  Found {len(composable_identifiers)} identifiers in composable.")
        else:
            print(f"  Composable file not found at {composable_path}.")

    # --- Scan codebase ---
    print(f"\nScanning codebase for files importing {mixin_path.name}...")
    importing_files = find_files_importing_mixin(project_root, mixin_path, config.skip_dirs)
    print(f"  Found {len(importing_files)} files.")

    # --- Build usage map for report ---
    usage_map: dict[str, list[str]] = {}
    for file_path in sorted(importing_files):
        relative_path = file_path.relative_to(project_root)
        used = find_used_members_in_file(file_path, all_member_names)
        usage_map[str(relative_path)] = used

    # --- Generate report ---
    print("Generating report...")
    report = build_audit_report(
        mixin_path=mixin_path,
        members=members,
        lifecycle_hooks=lifecycle_hooks,
        importing_files=importing_files,
        all_member_names=all_member_names,
        composable_path_arg=composable_path_resolved,
        composable_identifiers=composable_identifiers,
        composable_exists=composable_exists,
        project_root=project_root,
        usage_map=usage_map,
    )

    output_path = project_root / f"mixin_audit_{mixin_path.stem}.md"
    output_path.write_text(report)
    print(f"Report written to {output_path}")

    # --- Prompt for composable injection ---
    if importing_files and all_member_names:
        prompt_and_inject(
            importing_files=importing_files,
            all_member_names=all_member_names,
            mixin_path=mixin_path,
            composable_path_arg=composable_path_resolved,
            project_root=project_root,
        )
