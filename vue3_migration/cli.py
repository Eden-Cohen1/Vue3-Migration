"""
CLI entry point for the Vue Mixin Migration Tool.

Provides interactive menu and subcommands: scan, component, audit.
Replaces the original migrate.py subprocess-based delegation with
direct module imports.
"""

import os
import re
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



# =============================================================================
# Interactive Menu
# =============================================================================

def interactive_menu(config: MigrationConfig):
    """Show the main interactive menu when no arguments are provided."""

    print()
    print(f"  {bold('Vue Mixin Migration Tool')}")
    print(f"  {dim('Migrate Vue 2 mixins to Vue 3 composables.')}")
    print()
    print(f"  {bold('1.')} {green('Full project')}")
    print(f"     Migrate every component at once. Auto-patches and generates")
    print(f"     composables as needed. Shows a change summary before writing.\n")
    print(f"  {bold('2.')} {green('Pick a component')}")
    print(f"     Choose one component from a list. Migrate only that component.")
    print(f"     Safe for large projects -- low blast radius, easy to test.\n")
    print(f"  {bold('3.')} {green('Pick a mixin')}")
    print(f"     Choose one mixin. Fully retires it across all components that use it.")
    print(f"     Patches/generates the composable and updates every affected component.\n")
    print(f"  {bold('4.')} {green('Project status')}")
    print(f"     Read-only. Generates a detailed report of what's migrated,")
    print(f"     what's ready, and what's blocked. No files are changed.\n")
    print(f"  {bold('q.')} Quit\n")

    choice = input(f"  Choose (1/2/3/4/q): ").strip()
    print()

    if choice == "1":
        full_project_migration(config)
    elif choice == "2":
        pick_component_migration(config)
    elif choice == "3":
        pick_mixin_migration(config)
    elif choice == "4":
        project_status(config)
    elif choice.lower() == "q":
        return
    else:
        print(f"  {yellow('Invalid choice.')}")


# =============================================================================
# New CLI helpers and stubs (Task 1)
# =============================================================================

def _print_help():
    print(f"""
  {bold('Vue Mixin Migration Tool')}

  {bold('Usage:')}
    vue3-migration                       Interactive menu
    vue3-migration all                   Migrate entire project
    vue3-migration component <path>      Migrate one component
    vue3-migration mixin <name>          Retire one mixin across all components
    vue3-migration status                Generate project status report

  {bold('Examples:')}
    vue3-migration component src/components/UserProfile.vue
    vue3-migration mixin authMixin
""")


# ---------------------------------------------------------------------------
# Shared write/display helpers
# ---------------------------------------------------------------------------

def _show_change_summary(plan, project_root: Path) -> None:
    """Print human-readable change counts and per-file descriptions."""
    from .reporting.diff import format_change_list

    composable_count = sum(1 for c in plan.composable_changes if c.has_changes)
    component_count = sum(1 for c in plan.component_changes if c.has_changes)

    if composable_count:
        print(f"  Composables to patch/create: {yellow(str(composable_count))}")
    print(f"  Components to update:        {yellow(str(component_count))}")
    print()
    print(format_change_list(plan, project_root))


def _apply_plan(plan, project_root: Path) -> None:
    """Write all changed files and save a diff markdown report."""
    from .reporting.diff import write_diff_report

    written: list[Path] = []
    try:
        for change in plan.composable_changes:
            if change.has_changes:
                change.file_path.parent.mkdir(parents=True, exist_ok=True)
                change.file_path.write_text(change.new_content, encoding="utf-8")
                written.append(change.file_path)
                is_new = not change.original_content.strip()
                label = green("CREATED") if is_new else green("PATCHED")
                print(f"  {label}  {change.file_path.name}")
        for change in plan.component_changes:
            if change.has_changes:
                change.file_path.write_text(change.new_content, encoding="utf-8")
                written.append(change.file_path)
                print(f"  {green('MIGRATED')} {change.file_path.name}")
    except (KeyboardInterrupt, OSError):
        print(f"\n  {yellow('WARNING')}: Interrupted after {len(written)} file(s) written.")
        if written:
            print(f"  Written so far: {', '.join(f.name for f in written)}")
        print(f"  Run: git diff   to review.")
        print(f"  Run: git checkout . to undo all changes.")
        raise

    report_path = write_diff_report(plan, project_root)
    print(f"\n  {bold('Done.')} Diff report: {dim(str(report_path.name))}")
    print(f"  Review changes: git diff")


# ---------------------------------------------------------------------------
# Scanning helpers
# ---------------------------------------------------------------------------

def _scan_components_with_mixins(project_root: Path, config: MigrationConfig) -> list[dict]:
    """Return list of component info dicts for all .vue files that use mixins."""
    from .core.composable_search import collect_composable_stems, find_composable_dirs, mixin_has_composable

    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs, project_root=project_root)
    results: list[dict] = []

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
            stems = [resolve_mixin_stem(imports.get(n, "")) or n for n in mixin_names]
            covered = sum(1 for s in stems if mixin_has_composable(s, composable_stems))
            try:
                rel = filepath.relative_to(project_root)
            except ValueError:
                rel = filepath
            results.append({
                "rel_path": rel,
                "abs_path": filepath,
                "mixin_names": mixin_names,
                "mixin_stems": stems,
                "covered": covered,
                "total": len(stems),
            })

    results.sort(key=lambda c: -len(c["mixin_names"]))
    return results


def _scan_mixin_usage(project_root: Path, config: MigrationConfig) -> list[dict]:
    """Return list of mixin info dicts sorted by usage count."""
    from .core.composable_search import collect_composable_stems, find_composable_dirs, mixin_has_composable

    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs, project_root=project_root)
    mixin_counter: Counter[str] = Counter()

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
            imports = _parse_imports(source)
            for name in mixin_names:
                stem = resolve_mixin_stem(imports.get(name, "")) or name
                mixin_counter[stem] += 1

    return [
        {
            "stem": stem,
            "count": count,
            "has_composable": mixin_has_composable(stem, composable_stems),
        }
        for stem, count in mixin_counter.most_common()
    ]


# ---------------------------------------------------------------------------
# Task 4 — full_project_migration
# ---------------------------------------------------------------------------

def full_project_migration(config: MigrationConfig) -> None:
    from .workflows import auto_migrate_workflow

    print(f"\n{bold('Full project migration')}")
    print(f"  {dim('Scan -> patch composables -> inject setup() -> confirm -> write')}\n")

    plan = auto_migrate_workflow.run(config.project_root, config)

    if not plan.has_changes:
        print(f"  {green('Nothing to migrate.')} All components are already migrated or blocked.")
        return

    _show_change_summary(plan, config.project_root)

    answer = input(f"\n{bold('Apply all changes?')} (y/n): ").strip().lower()
    if answer != "y":
        print("  Aborted. No files were written.")
        return

    _apply_plan(plan, config.project_root)


# ---------------------------------------------------------------------------
# Task 5 — component_migration / pick_component_migration
# ---------------------------------------------------------------------------

def pick_component_migration(config: MigrationConfig) -> None:
    project_root = config.project_root
    print(f"\n{bold('Pick a component to migrate')}\n")
    print(f"  {dim('Scanning...')}\n")

    components = _scan_components_with_mixins(project_root, config)

    if not components:
        print(f"  {green('No components with mixins found.')} Migration complete!\n")
        return

    for idx, comp in enumerate(components, 1):
        covered, total = comp["covered"], comp["total"]
        if covered == total:
            cov_str = green("all composables found")
        elif covered > 0:
            cov_str = yellow(f"{covered}/{total} composables found")
        else:
            cov_str = dim("no composables yet (will be generated)")

        print(f"  {bold(str(idx) + '.')} {str(comp['rel_path'])}")
        print(f"     {dim(', '.join(comp['mixin_stems']))}  --  {cov_str}")

    print(f"\n  Enter a number (1-{len(components)}), component name/path, or {bold('q')} to go back.\n")
    choice = input("  > ").strip()

    if not choice or choice.lower() == "q":
        return
    comp = None
    try:
        idx = int(choice)
        if 1 <= idx <= len(components):
            comp = components[idx - 1]
        else:
            print(f"  {yellow('Number out of range.')}")
            return
    except ValueError:
        search = choice if choice.endswith('.vue') else choice + '.vue'
        matches = [
            c for c in components
            if c['rel_path'].name.lower() == search.lower()
            or search.lower() in str(c['rel_path']).lower()
        ]
        if len(matches) == 1:
            comp = matches[0]
        elif len(matches) > 1:
            print(f"  {yellow('Multiple matches:')}")
            for i, m in enumerate(matches, 1):
                print(f"    {bold(str(i) + '.')} {str(m['rel_path'])}")
            pick = input(f"\n  Select (1-{len(matches)}) or {bold('q')} to go back: ").strip()
            if not pick or pick.lower() == "q":
                return
            try:
                pick_idx = int(pick)
                if 1 <= pick_idx <= len(matches):
                    comp = matches[pick_idx - 1]
                else:
                    print(f"  {yellow('Number out of range.')}")
                    return
            except ValueError:
                print(f"  {yellow('Please enter a number.')}")
                return
        else:
            print(f"  {yellow('No component found matching:')} {choice}")
            return

    print(f"\n{bold('Migrating:')} {green(str(comp['rel_path']))}\n")
    _run_component_migration(comp["abs_path"], config)


def component_migration(path: str, config: MigrationConfig) -> None:
    project_root = config.project_root
    target = Path(path).resolve()
    if not target.is_file():
        target = (project_root / path).resolve()
    if not target.is_file():
        print(f"  {yellow('Component not found:')} {path}")
        return
    print(f"\n{bold('Migrating:')} {green(target.name)}\n")
    _run_component_migration(target, config)


def _run_component_migration(component_path: Path, config: MigrationConfig) -> None:
    from .workflows import auto_migrate_workflow

    plan = auto_migrate_workflow.run_scoped(
        config.project_root, config, component_path=component_path
    )

    if not plan.has_changes:
        print(f"  {green('Nothing to migrate.')} Component is already migrated or no composable match found.")
        return

    _show_change_summary(plan, config.project_root)

    answer = input(f"\n{bold('Apply changes?')} (y/n): ").strip().lower()
    if answer != "y":
        print("  Aborted. No files were written.")
        return

    _apply_plan(plan, config.project_root)


# ---------------------------------------------------------------------------
# Task 6 — mixin_migration / pick_mixin_migration
# ---------------------------------------------------------------------------

def pick_mixin_migration(config: MigrationConfig) -> None:
    project_root = config.project_root
    print(f"\n{bold('Pick a mixin to retire')}\n")
    print(f"  {dim('Scanning...')}\n")

    mixins = _scan_mixin_usage(project_root, config)

    if not mixins:
        print(f"  {green('No mixins in use.')} Migration complete!\n")
        return

    print(f"  {'#':<4} {'Mixin':<40} {'Components':<12} Composable")
    print(f"  {'-'*4} {'-'*40} {'-'*12} {'-'*20}")
    for idx, m in enumerate(mixins, 1):
        comp_label = green("found") if m["has_composable"] else dim("will be generated")
        component_word = "component" if m["count"] == 1 else "components"
        print(f"  {idx:<4} {m['stem']:<40} {m['count']} {component_word:<9} {comp_label}")

    print(f"\n  Enter a number (1-{len(mixins)}), mixin name, or {bold('q')} to go back.\n")
    choice = input("  > ").strip()

    if not choice or choice.lower() == "q":
        return
    mixin = None
    try:
        idx = int(choice)
        if 1 <= idx <= len(mixins):
            mixin = mixins[idx - 1]
        else:
            print(f"  {yellow('Number out of range.')}")
            return
    except ValueError:
        search = choice.lower()
        matches = [m for m in mixins if m['stem'].lower() == search or search in m['stem'].lower()]
        if len(matches) == 1:
            mixin = matches[0]
        elif len(matches) > 1:
            print(f"  {yellow('Multiple matches:')}")
            for i, m in enumerate(matches, 1):
                print(f"    {bold(str(i) + '.')} {m['stem']}")
            pick = input(f"\n  Select (1-{len(matches)}) or {bold('q')} to go back: ").strip()
            if not pick or pick.lower() == "q":
                return
            try:
                pick_idx = int(pick)
                if 1 <= pick_idx <= len(matches):
                    mixin = matches[pick_idx - 1]
                else:
                    print(f"  {yellow('Number out of range.')}")
                    return
            except ValueError:
                print(f"  {yellow('Please enter a number.')}")
                return
        else:
            print(f"  {yellow('No mixin found matching:')} {choice}")
            return

    component_word = "component" if mixin["count"] == 1 else "components"
    print(f"\n{bold('Retiring:')} {green(mixin['stem'])} across {yellow(str(mixin['count']))} {component_word}\n")
    _run_mixin_migration(mixin["stem"], config)


def mixin_migration(name: str, config: MigrationConfig) -> None:
    # Strip file extension and path if user passed a file path
    stem = Path(name).stem
    print(f"\n{bold('Retiring mixin:')} {green(stem)}\n")
    _run_mixin_migration(stem, config)


def _run_mixin_migration(mixin_stem: str, config: MigrationConfig) -> None:
    from .workflows import auto_migrate_workflow

    plan = auto_migrate_workflow.run_scoped(
        config.project_root, config, mixin_stem=mixin_stem
    )

    if not plan.has_changes:
        print(f"  {green('Nothing to migrate.')} No ready components found for this mixin.")
        return

    component_count = sum(1 for c in plan.component_changes if c.has_changes)
    composable_count = sum(1 for c in plan.composable_changes if c.has_changes)
    if component_count:
        component_word = "component" if component_count == 1 else "components"
        print(f"  This will update {yellow(str(component_count))} {component_word}.\n")
    elif composable_count:
        print(f"  No components use this mixin. Will generate composable only.\n")

    _show_change_summary(plan, config.project_root)

    answer = input(f"\n{bold('Apply changes?')} (y/n): ").strip().lower()
    if answer != "y":
        print("  Aborted. No files were written.")
        return

    _apply_plan(plan, config.project_root)


# ---------------------------------------------------------------------------
# Task 7 — project_status
# ---------------------------------------------------------------------------

def project_status(config: MigrationConfig) -> None:
    from .reporting.markdown import generate_status_report
    from datetime import datetime

    print(f"\n{bold('Project status')}")
    print(f"  {dim('Scanning project...')}\n")

    report = generate_status_report(config.project_root, config)

    # Print concise terminal summary (first 20 lines = header + summary + mixin table start)
    for line in report.splitlines()[:20]:
        try:
            print(f"  {line}")
        except UnicodeEncodeError:
            print(f"  {line.encode('ascii', errors='replace').decode('ascii')}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = config.project_root / f"migration-status-{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n  {bold('Full report saved to:')} {green(str(report_path))}")



# =============================================================================
# CLI Entry Point
# =============================================================================

def main(argv: list[str] | None = None):
    import argparse
    import sys
    args = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", default=None)
    parser.add_argument("--regenerate", "-R", action="store_true", default=False)
    known, args = parser.parse_known_args(args)
    project_root = Path(known.root).resolve() if known.root else Path.cwd()
    config = MigrationConfig(project_root=project_root, regenerate=known.regenerate)

    if not args:
        interactive_menu(config)
        return

    command = args[0].lower()

    if command == "all":
        full_project_migration(config)
    elif command == "component":
        if len(args) < 2:
            print(f"\n  Usage: vue3-migration component <path/to/Component.vue>\n")
            return
        component_migration(args[1], config)
    elif command == "mixin":
        if len(args) < 2:
            print(f"\n  Usage: vue3-migration mixin <mixinName>\n")
            return
        mixin_migration(args[1], config)
    elif command == "status":
        project_status(config)
    elif command in ("help", "--help", "-h"):
        _print_help()
    else:
        print(f"\n  {yellow('Unknown command')}: {command}")
        print(f"  Run {bold('vue3-migration --help')} for available commands.\n")
