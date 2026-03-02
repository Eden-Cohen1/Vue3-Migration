"""
CLI entry point for the Vue Mixin Migration Tool.

Provides interactive menu and subcommands: scan, component, audit.
Replaces the original migrate.py subprocess-based delegation with
direct module imports.
"""

import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from .core.component_analyzer import parse_imports, parse_mixins_array
from .core.composable_search import (
    collect_composable_stems,
    find_composable_dirs,
    mixin_has_composable,
)
from .core.file_resolver import resolve_mixin_stem
from .models import MigrationConfig
from .reporting.terminal import bold, cyan, dim, green, red, yellow
from .workflows import component_workflow, mixin_workflow


# =============================================================================
# Scan
# =============================================================================

def _parse_mixins_array(source: str) -> list[str]:
    """Quick extraction of mixin names from `mixins: [A, B, C]`."""
    return parse_mixins_array(source)


def _parse_imports(source: str) -> dict[str, str]:
    """Parse import statements. Returns { local_name: import_path }."""
    return parse_imports(source)


def _find_mixin_file(mixin_stem: str, project_root: Path) -> Optional[Path]:
    """Try to find a mixin file by its stem name."""
    for dirpath, _, filenames in os.walk(project_root):
        rel = Path(dirpath).relative_to(project_root)
        if any(p in {"node_modules", "dist", ".git"} for p in rel.parts):
            continue
        for fn in filenames:
            fp = Path(dirpath) / fn
            if fp.suffix in (".js", ".ts") and fp.stem == mixin_stem:
                return fp
    return None


def scan_project(project_root: Path, config: MigrationConfig):
    """Walk the project and find every component that still uses mixins."""

    print(f"\n{bold('Scanning project for components with mixins...')}\n")

    components = []  # list of (rel_path, mixin_local_names, mixin_stems)

    for dirpath, _, filenames in os.walk(project_root):
        rel_dir = Path(dirpath).relative_to(project_root)
        if any(part in config.skip_dirs for part in rel_dir.parts):
            continue

        for fn in filenames:
            if not fn.endswith(".vue"):
                continue

            filepath = Path(dirpath) / fn
            try:
                source = filepath.read_text(errors="ignore")
            except Exception:
                continue

            mixin_names = _parse_mixins_array(source)
            if not mixin_names:
                continue

            imports = _parse_imports(source)
            stems = []
            for name in mixin_names:
                imp = imports.get(name, "")
                stems.append(resolve_mixin_stem(imp) if imp else name)

            try:
                rel = filepath.relative_to(project_root)
            except ValueError:
                rel = filepath

            components.append((rel, mixin_names, stems))

    if not components:
        print(f"{green('No components with mixins found.')} Migration complete!\n")
        return

    # Sort by number of mixins (most first)
    components.sort(key=lambda c: -len(c[1]))

    # Count mixin frequencies
    mixin_counter: Counter[str] = Counter()
    for _, _, stems in components:
        for stem in stems:
            mixin_counter[stem] += 1

    # Check which composables already exist
    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs)

    # --- Display results ---
    print(f"{bold('Project Overview')}")
    print(f"  Components with mixins:  {yellow(str(len(components)))}")
    print(f"  Unique mixins in use:    {yellow(str(len(mixin_counter)))}")
    print(f"  Composables directories: {len(composable_dirs)}")
    print()

    # Mixin frequency table
    print(f"{bold('Mixin Usage Across Project')}")
    print(f"  {'Mixin':<40} {'Used in':<10} {'Composable?'}")
    print(f"  {'-' * 40} {'-' * 10} {'-' * 12}")

    for mixin_stem, count in mixin_counter.most_common():
        has_comp = mixin_has_composable(mixin_stem, composable_stems)
        comp_status = green("found") if has_comp else dim("not found")
        print(f"  {mixin_stem:<40} {count:<10} {comp_status}")

    print()

    # Component list
    print(f"{bold('Components')}")
    print()

    for idx, (rel_path, mixin_names, stems) in enumerate(components, 1):
        mixin_count = len(mixin_names)
        color = green if mixin_count <= 2 else (yellow if mixin_count <= 4 else red)
        count_str = color(f"{mixin_count} mixin{'s' if mixin_count != 1 else ''}")

        covered = sum(1 for s in stems if mixin_has_composable(s, composable_stems))
        if covered == len(stems):
            coverage = green("all composables found")
        elif covered > 0:
            coverage = yellow(f"{covered}/{len(stems)} composables found")
        else:
            coverage = dim("no composables yet")

        print(f"  {bold(str(idx) + '.')} {green(str(rel_path))}")
        print(f"     {count_str} -- {coverage}")
        print(f"     {dim(', '.join(stems))}")

    # Actions
    print(f"\n{bold('What would you like to do?')}\n")
    print(f"  Enter a {bold('number')} (1-{len(components)}) to migrate that component.")
    print(f"  Enter a {bold('mixin name')} to audit it across the project.")
    print(f"  Enter {bold('q')} to quit.\n")

    choice = input("  > ").strip()

    if not choice or choice.lower() == "q":
        return

    # Number -> migrate component
    try:
        idx = int(choice)
        if 1 <= idx <= len(components):
            rel_path = components[idx - 1][0]
            print()
            component_workflow.run(str(rel_path), config)
            return
        else:
            print(f"  {yellow('Number out of range.')}")
            return
    except ValueError:
        pass

    # Text -> try to match a mixin name
    matched_stem = None
    for mixin_stem in mixin_counter:
        if choice.lower() == mixin_stem.lower():
            matched_stem = mixin_stem
            break

    if not matched_stem:
        for mixin_stem in mixin_counter:
            if choice.lower() in mixin_stem.lower():
                matched_stem = mixin_stem
                break

    if matched_stem:
        mixin_file = _find_mixin_file(matched_stem, project_root)
        if mixin_file:
            print(f"\n  Auditing {green(matched_stem)} -> {green(str(mixin_file))}\n")
            mixin_workflow.run(str(mixin_file), config=config)
        else:
            print(f"\n  {yellow('Could not locate the mixin file for')} {matched_stem}.")
            user_path = input(f"  Enter the mixin file path: ").strip()
            if user_path:
                mixin_workflow.run(user_path, config=config)
    else:
        print(f"  {yellow('No matching mixin found for')} '{choice}'.")


# =============================================================================
# Interactive Menu
# =============================================================================

def interactive_menu(config: MigrationConfig):
    """Show the main interactive menu when no arguments are provided."""

    print()
    print(f"  {bold('Vue Mixin Migration Tool')}")
    print(f"  {dim('Helps you migrate Vue 2 mixins to Vue 3 composables.')}")
    print()
    print(f"  This tool supports two migration workflows:\n")
    print(f"  {bold('1.')} {green('Scan project')}")
    print(f"     Get an overview of all components still using mixins,")
    print(f"     see which composables already exist, and pick a component")
    print(f"     or mixin to work on next.\n")
    print(f"  {bold('2.')} {green('Migrate a component')}")
    print(f"     Given a single .vue file, find all its mixins, match them")
    print(f"     to composables, check coverage, and inject setup() for")
    print(f"     every mixin that has a ready composable.\n")
    print(f"  {bold('3.')} {green('Audit a mixin')}")
    print(f"     Given a mixin file, find every component that uses it,")
    print(f"     show which members each component relies on, and compare")
    print(f"     against a composable to see what's covered.\n")
    print(f"  {bold('4.')} {green('Auto-migrate (full project)')}")
    print(f"     Scan the entire project, auto-patch composables for blocked cases,")
    print(f"     convert lifecycle hooks to Vue 3, show a dry-run diff, then")
    print(f"     write all changes after a single confirmation.\n")
    print(f"  {bold('q.')} Quit\n")

    choice = input(f"  Choose (1/2/3/4/q): ").strip()
    print()

    if choice == "1":
        scan_project(config.project_root, config)

    elif choice == "2":
        print(f"  {bold('Migrate a component')}")
        print(f"  {dim('Enter the path to a .vue file relative to the project root.')}\n")
        path = input(f"  Component path: ").strip()
        if path:
            component_workflow.run(path, config)
        else:
            print(f"  {yellow('No path provided.')}")

    elif choice == "3":
        print(f"  {bold('Audit a mixin')}")
        print(f"  {dim('Enter the path to a mixin .js/.ts file.')}")
        print(f"  {dim('Optionally, also provide a composable path to compare against.')}\n")
        mixin_path = input(f"  Mixin path: ").strip()
        if not mixin_path:
            print(f"  {yellow('No path provided.')}")
            return
        composable_path = input(f"  Composable path (optional, press Enter to skip): ").strip()
        mixin_workflow.run(mixin_path, composable_path or None, config)

    elif choice == "4":
        auto_migrate(config.project_root, config)

    elif choice.lower() == "q":
        return

    else:
        print(f"  {yellow('Invalid choice.')}")


# =============================================================================
# Auto-migrate
# =============================================================================

def auto_migrate(project_root: Path, config: MigrationConfig) -> None:
    """Run auto-migrate: scan, patch composables, inject setup(), show diff, confirm."""
    from .workflows import auto_migrate_workflow
    from .reporting.diff import print_diff_summary

    print(f"\n{bold('Auto-migrate: full project migration')}")
    print(f"  {dim('Scan → patch composables → inject setup() → dry-run diff → confirm')}\n")

    plan = auto_migrate_workflow.run(project_root, config)

    if not plan.has_changes:
        print(f"{green('Nothing to migrate.')} All components are already migrated or have no matching composable.")
        return

    composable_count = sum(1 for c in plan.composable_changes if c.has_changes)
    component_count = sum(1 for c in plan.component_changes if c.has_changes)
    print(f"  Composables to patch: {yellow(str(composable_count))}")
    print(f"  Components to update: {yellow(str(component_count))}\n")

    print_diff_summary(plan.all_changes, project_root)

    answer = input(f"\n{bold('Apply all changes?')} (y/n): ").strip().lower()
    if answer != "y":
        print("Aborted. No files were written.")
        return

    # R-8: wrap write loop with recovery message on interruption
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
    except (KeyboardInterrupt, OSError) as e:
        print(f"\n  {yellow('WARNING')}: Migration interrupted after {len(written)} file(s) written.")
        if written:
            print(f"  Already written: {', '.join(f.name for f in written)}")
        print(f"  Run: git diff to review. Run: git checkout . to undo.")
        raise

    print(f"\n{bold('Done.')} Review the diff and test your application.")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    config = MigrationConfig()

    # No arguments -> interactive menu
    if len(sys.argv) < 2:
        interactive_menu(config)
        return

    command = sys.argv[1].lower()

    if command == "scan":
        scan_project(config.project_root, config)

    elif command == "component":
        if len(sys.argv) < 3:
            print(f"\n  {bold('Migrate a component')}")
            print(f"  {dim('Finds all mixins in a component, matches them to composables,')}")
            print(f"  {dim('and injects setup() for those with full coverage.')}\n")
            print(f"  Usage: python -m vue3_migration component <path/to/Component.vue>\n")
            return
        component_workflow.run(sys.argv[2], config)

    elif command == "audit":
        if len(sys.argv) < 3:
            print(f"\n  {bold('Audit a mixin')}")
            print(f"  {dim('Finds every component using a mixin, shows member usage,')}")
            print(f"  {dim('and compares against a composable if provided.')}\n")
            print(f"  Usage: python -m vue3_migration audit <mixin_path> [composable_path]\n")
            return
        composable_arg = sys.argv[3] if len(sys.argv) > 3 else None
        mixin_workflow.run(sys.argv[2], composable_arg, config)

    elif command == "auto-migrate":
        auto_migrate(config.project_root, config)

    elif command in ("help", "--help", "-h"):
        print(f"""
  {bold('Vue Mixin Migration Tool')}

  {bold('Usage:')}
    python -m vue3_migration                           Interactive menu
    python -m vue3_migration scan                      Scan project for migration status
    python -m vue3_migration component <path.vue>      Migrate one component
    python -m vue3_migration audit <mixin> [composable] Audit one mixin
    python -m vue3_migration auto-migrate              Fully automated: patch composables, inject setup(), show diff

  {bold('Workflow:')}
    1. Run {green('scan')} to see which components still use mixins
       and which composables are already available.

    2. Pick a component and run {green('component')} to migrate it.
       The tool will match each mixin to a composable, report what's
       missing, and inject setup() for every ready composable.

    3. If you want to focus on a single mixin across the codebase,
       run {green('audit')} to see every component that depends on it
       and what members they use.

    4. Run {green('auto-migrate')} for a fully automated project-wide migration.
       Scans all components, auto-patches composables for blocked cases,
       converts lifecycle hooks to Vue 3, shows a dry-run diff, and writes
       all changes after a single 'y' confirmation.
""")

    else:
        print(f"\n  {yellow('Unknown command')}: {command}")
        print(f"  Run {bold('python -m vue3_migration help')} to see available commands.\n")
