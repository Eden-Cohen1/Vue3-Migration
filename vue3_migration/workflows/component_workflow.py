"""
Component-centric migration workflow.

Analyzes a single Vue component's mixins, matches them to composables,
generates a migration report, and optionally injects setup() for
ready composables.
"""

import re
import sys
from pathlib import Path
from typing import Optional

from ..core.component_analyzer import (
    extract_own_members,
    find_used_members,
    parse_imports,
    parse_mixins_array,
)
from ..core.composable_analyzer import (
    extract_all_identifiers,
    extract_function_name,
    extract_return_keys,
)
from ..core.composable_search import (
    find_composable_dirs,
    generate_candidates,
    search_for_composable,
)
from ..core.file_resolver import (
    compute_import_path,
    resolve_import_path,
    try_resolve_with_extensions,
)
from ..core.mixin_analyzer import extract_lifecycle_hooks, extract_mixin_members
from ..models import (
    ComposableCoverage,
    FileChange,
    MigrationConfig,
    MigrationStatus,
    MixinEntry,
    MixinMembers,
)
from ..reporting.markdown import build_component_report
from ..reporting.terminal import bold, cyan, dim, green, red, yellow
from ..transform.injector import (
    add_composable_import,
    inject_setup,
    remove_import_line,
    remove_mixin_from_array,
)


def analyze_mixin(
    local_name: str,
    import_path: str,
    component_path: Path,
    component_source: str,
    composable_dirs: list[Path],
    project_root: Path,
    component_own_members: set[str],
) -> Optional[MixinEntry]:
    """Analyze a single mixin: resolve file, extract members, find composable."""

    # -- Resolve mixin file --
    mixin_file = resolve_import_path(import_path, component_path)
    if not mixin_file:
        print(f"  {yellow('WARNING')}: Could not resolve file for '{import_path}'. Skipping.")
        return None

    print(f"  File: {green(str(mixin_file))}")

    # -- Extract mixin members and hooks --
    mixin_source = mixin_file.read_text(errors="ignore")
    members_dict = extract_mixin_members(mixin_source)
    members = MixinMembers(**members_dict)
    hooks = extract_lifecycle_hooks(mixin_source)
    all_member_names = members.all_names
    print(f"  {len(all_member_names)} members, {len(hooks)} lifecycle hooks")

    # -- Find which members the component actually uses --
    used = find_used_members(component_source, all_member_names)
    print(f"  {len(used)} members used by component")

    entry = MixinEntry(
        local_name=local_name,
        mixin_path=mixin_file,
        mixin_stem=mixin_file.stem,
        members=members,
        lifecycle_hooks=hooks,
        used_members=used,
    )

    # -- Search for matching composable (skip if no members are used) --
    if not used:
        print(f"  {dim('No members used -- composable search skipped.')}")
        entry.compute_status()
        return entry

    candidates = generate_candidates(mixin_file.stem)
    print(f"  Looking for: {cyan(', '.join(candidates))}")

    matches = search_for_composable(mixin_file.stem, composable_dirs)
    composable_file = None

    if len(matches) == 1:
        composable_file = matches[0]
        print(f"  Found: {green(str(composable_file))}")
    elif len(matches) > 1:
        print(f"  {yellow('Multiple candidates found')}:")
        for i, fp in enumerate(matches, 1):
            print(f"    {i}. {green(str(fp))}")
        choice = input(f"  Pick one (1-{len(matches)}), or 0 for none: ").strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(matches):
                composable_file = matches[idx - 1]
        except ValueError:
            pass
    else:
        print(f"  {yellow('No composable found automatically.')}")

    # If still no match, ask user
    if not composable_file:
        answer = input(f"  Is there a composable for {green(mixin_file.stem)}? (y/n): ").strip().lower()
        if answer == "y":
            user_path = input("  Enter composable path: ").strip()
            if user_path:
                resolved = resolve_import_path(user_path, component_path)
                if not resolved:
                    resolved = try_resolve_with_extensions((project_root / user_path).resolve())
                if resolved:
                    composable_file = resolved
                else:
                    print(f"  {red('File not found')}: {user_path}")

    # -- Analyze composable coverage --
    if composable_file:
        comp_source = composable_file.read_text(errors="ignore")
        fn_name = extract_function_name(comp_source)
        if not fn_name:
            print(f"  {yellow('Could not detect function name.')}")
            fn_name = input("  Enter function name (e.g. useSelection): ").strip()

        if fn_name:
            all_identifiers = extract_all_identifiers(comp_source)
            return_keys = extract_return_keys(comp_source)
            import_path_str = compute_import_path(composable_file, project_root)

            coverage = ComposableCoverage(
                file_path=composable_file,
                fn_name=fn_name,
                import_path=import_path_str,
                all_identifiers=all_identifiers,
                return_keys=return_keys,
            )
            classification = coverage.classify_members(used, component_own_members)

            entry.composable = coverage
            entry.classification = classification

            status = "READY" if classification.is_ready else "BLOCKED"
            status_colored = green(status) if status == "READY" else red(status)
            print(f"  Status: {status_colored}", end="")
            if classification.truly_missing:
                print(f" | {red('Missing')}: {', '.join(classification.truly_missing)}", end="")
            if classification.truly_not_returned:
                print(f" | {yellow('Not returned')}: {', '.join(classification.truly_not_returned)}", end="")
            if classification.overridden:
                print(f" | {dim('Overridden by component')}: {', '.join(classification.overridden)}", end="")
            if classification.overridden_not_returned:
                print(f" | {dim('Overridden (not returned)')}: {', '.join(classification.overridden_not_returned)}", end="")
            print()

    entry.compute_status()
    return entry


def plan_injection(
    component_path: Path,
    entries_to_inject: list[MixinEntry],
) -> FileChange:
    """Plan injection changes without writing to disk.

    Returns a FileChange with original and modified content.
    """
    content = component_path.read_text(errors="ignore")
    original = content
    changes: list[str] = []

    # Step 1: Swap imports
    for entry in entries_to_inject:
        new = remove_import_line(content, entry.mixin_stem)
        if new != content:
            changes.append(f"Removed import for {entry.mixin_stem}")
            content = new

        injectable = _get_injectable_members(entry)
        if injectable and entry.composable:
            comp = entry.composable
            new = add_composable_import(content, comp.fn_name, comp.import_path)
            if new != content:
                changes.append(f"Added import {{ {comp.fn_name} }}")
                content = new
        elif not injectable:
            changes.append(f"Skipped composable import for {entry.mixin_stem} (no injectable members)")

    # Step 2: Remove processed mixins from the mixins: [] array
    for entry in entries_to_inject:
        new = remove_mixin_from_array(content, entry.local_name)
        if new != content:
            changes.append(f"Removed {entry.local_name} from mixins array")
            content = new

    # Step 3: Create or merge setup()
    composable_calls = [
        (entry.composable.fn_name, _get_injectable_members(entry))
        for entry in entries_to_inject
        if entry.composable and _get_injectable_members(entry)
    ]

    if composable_calls:
        new = inject_setup(content, composable_calls)
        if new != content:
            fn_names = [c[0] for c in composable_calls]
            all_members = [m for _, members in composable_calls for m in members]
            changes.append(f"setup() with {', '.join(fn_names)} -> {{ {', '.join(all_members)} }}")
            content = new

    # Clean up excessive blank lines
    if content != original:
        content = re.sub(r"\n{3,}", "\n\n", content)

    return FileChange(
        file_path=component_path,
        original_content=original,
        new_content=content,
        changes=changes,
    )


def apply_changes(file_change: FileChange) -> None:
    """Write planned changes to disk."""
    if file_change.has_changes:
        file_change.file_path.write_text(file_change.new_content, encoding="utf-8")


def _get_injectable_members(entry: MixinEntry) -> list[str]:
    """Get the list of members that should be destructured from the composable."""
    if entry.classification:
        return entry.classification.injectable
    return entry.used_members


def run(component_arg: str, config: MigrationConfig | None = None):
    """Main entry point for the component migration workflow."""
    if config is None:
        config = MigrationConfig()

    project_root = config.project_root
    component_path = Path(component_arg).resolve()
    if not component_path.is_file():
        sys.exit(f"Component not found: {component_path}")

    # ---- Phase 1: Analyze ----
    print(f"Analyzing: {green(component_arg)}")
    component_source = component_path.read_text(errors="ignore")

    all_imports = parse_imports(component_source)
    mixin_names = parse_mixins_array(component_source)

    if not mixin_names:
        sys.exit("No mixins found in this component.")

    print(f"Found {bold(str(len(mixin_names)))} mixin(s): {cyan(', '.join(mixin_names))}\n")

    # Scan all Composables directories once
    print("Scanning for Composables directories...")
    composable_dirs = find_composable_dirs(project_root)
    print(f"Found {bold(str(len(composable_dirs)))} director(ies).\n")

    # Extract component's own members for override detection
    component_own_members = extract_own_members(component_source)

    # Analyze each mixin
    mixin_entries: list[MixinEntry] = []
    for local_name in mixin_names:
        print(f"[{bold(local_name)}]")
        import_path = all_imports.get(local_name)
        if not import_path:
            print(f"  {yellow('WARNING')}: No import statement found for {local_name}. Skipping.")
            continue

        entry = analyze_mixin(
            local_name, import_path, component_path,
            component_source, composable_dirs, project_root,
            component_own_members,
        )
        if entry:
            mixin_entries.append(entry)

    if not mixin_entries:
        sys.exit("No mixins could be processed.")

    # ---- Phase 2: Report ----
    print("\n" + "=" * 60)
    print("Generating report...")

    report = build_component_report(component_path, mixin_entries, project_root)
    report_path = project_root / f"migration_{component_path.stem}.md"
    report_path.write_text(report)
    print(f"Report: {green(str(report_path))}")

    # ---- Phase 3: Inject ----

    # Split into ready vs blocked
    ready = [e for e in mixin_entries if e.status == MigrationStatus.READY]
    blocked = [e for e in mixin_entries if e.status != MigrationStatus.READY]

    if not ready and not blocked:
        print(f"\n{yellow('No mixins are ready for injection.')} Fix the issues in the report and re-run.")
        return

    # Show what's blocked
    if blocked:
        print(f"\n{yellow(str(len(blocked)))} mixin(s) still need work:")
        for e in blocked:
            comp = e.composable
            cls = e.classification
            detail_parts = []
            if comp and cls:
                if cls.truly_missing:
                    detail_parts.append(f"{red('missing')}: {', '.join(cls.truly_missing)}")
                if cls.truly_not_returned:
                    detail_parts.append(f"{yellow('not returned')}: {', '.join(cls.truly_not_returned)}")
            else:
                detail_parts.append(yellow("no composable found"))
            detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
            print(f"  - {red(e.mixin_stem)}{detail}")

    # Show what's ready
    if ready:
        label = (
            f"\n{green(str(len(ready)))} mixin(s) are ready:"
            if blocked
            else f"\nAll {green(str(len(ready)))} mixin(s) are ready:"
        )
        print(label)

    for e in ready:
        if not e.used_members:
            print(f"  - {green(e.mixin_stem)} {dim('(no members used -- will just remove mixin)')}")
        else:
            comp = e.composable
            injectable = _get_injectable_members(e)
            override_count = len(e.classification.overridden) + len(e.classification.overridden_not_returned) if e.classification else 0
            override_note = f" {dim(f'({override_count} overridden by component)')}" if override_count else ""
            print(f"  - {green(e.mixin_stem)} -> {cyan(comp.fn_name)}() ({len(injectable)} members){override_note}")

    # --- Action prompt ---
    if blocked:
        print(f"\n{bold('What would you like to do?')}")
        print(f"  {bold('a')}. Auto-migrate — auto-patch composables for blocked mixins, then inject all")
        if ready:
            print(f"  {bold('r')}. Inject ready only — inject the {green(str(len(ready)))} ready mixin(s), leave {yellow(str(len(blocked)))} blocked")
        print(f"  {bold('q')}. Skip\n")
        choice = input("  > ").strip().lower()
    else:
        choice = input(f"\nInject all composables? (y/n): ").strip().lower()
        if choice == "y":
            choice = "r"  # treat as inject-ready (all are ready)

    if choice == "a":
        from . import auto_migrate_workflow
        from ..reporting.diff import print_diff_summary

        plan = auto_migrate_workflow.run_scoped(project_root, config, component_path=component_path)
        if not plan.has_changes:
            print(f"\n{green('Nothing to auto-migrate.')} No READY entries found after patching.")
            return

        composable_count = sum(1 for c in plan.composable_changes if c.has_changes)
        component_count = sum(1 for c in plan.component_changes if c.has_changes)
        if composable_count:
            print(f"\n  Composables to patch: {yellow(str(composable_count))}")
        print(f"  Components to update: {yellow(str(component_count))}\n")

        print_diff_summary(plan.all_changes, project_root)

        confirm = input(f"\n{bold('Apply all changes?')} (y/n): ").strip().lower()
        if confirm != "y":
            print("Aborted. No files were written.")
            return

        written: list[Path] = []
        try:
            for change in plan.composable_changes:
                if change.has_changes:
                    change.file_path.write_text(change.new_content, encoding="utf-8")
                    written.append(change.file_path)
                    print(f"  {green('PATCHED')}  {change.file_path.name}")
            for change in plan.component_changes:
                if change.has_changes:
                    change.file_path.write_text(change.new_content, encoding="utf-8")
                    written.append(change.file_path)
                    print(f"  {green('MIGRATED')} {change.file_path.name}")
        except (KeyboardInterrupt, OSError):
            print(f"\n  {yellow('WARNING')}: Interrupted after {len(written)} file(s) written.")
            if written:
                print(f"  Already written: {', '.join(f.name for f in written)}")
            print(f"  Run: git diff to review. Run: git checkout . to undo.")
            raise

    elif choice == "r":
        if not ready:
            print(f"\n{yellow('No mixins are ready for injection.')} Fix the issues in the report and re-run.")
            return

        print("\nInjecting...")
        file_change = plan_injection(component_path, ready)

        if file_change.has_changes:
            apply_changes(file_change)
            print(f"\n{green('Changes applied')}:")
            for change in file_change.changes:
                print(f"  - {change}")
        else:
            print("\nNo changes needed.")

    else:
        print("Skipped.")
        return

    print(f"\n{bold('Done.')} Review the changes and test your application.")
