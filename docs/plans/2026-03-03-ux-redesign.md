# UX Redesign: Simplified Migration Menu Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the CLI from 4 overlapping options to a clean "one action, pick your scope" model with 4 clearly distinct flows: full project, pick a component, pick a mixin, and project status.

**Architecture:** The core migration engine (`auto_migrate_workflow`, `composable_patcher`, `injector`, etc.) is untouched. All changes are in the presentation layer: `cli.py` (menu, dispatch, workflow functions) and `reporting/` (human-readable change summaries, markdown diff files, status reports). The old `component_workflow` and `mixin_workflow` are removed from the CLI dispatch; `auto_migrate_workflow.run()` and `run_scoped()` become the sole migration engine called from the menu.

**Tech Stack:** Python 3.9+, pathlib, difflib (stdlib), existing vue3_migration modules

---

## Confirmed Design: Approach A — "One Action, Pick Your Scope"

The interactive menu always looks like:

```
  Vue Mixin Migration Tool
  Migrate Vue 2 mixins to Vue 3 composables.

  1. Full project      — migrate every component at once
  2. Pick a component  — choose one from a list, low blast radius
  3. Pick a mixin      — fully retire one mixin across all its components
  4. Project status    — read-only report, no files changed

  q. Quit
```

### Flow: Option 1 — Full project
1. Scan entire project
2. Auto-patch composables with missing members (additive)
3. Auto-generate composables for mixins with none
4. Inject `setup()` into every component (adds composable import, removes mixin import, removes from `mixins: []`)
5. Show human-readable change list per file in terminal
6. `Apply all changes? (y/n)`
7. Write files + save diff to `migration-diff-<timestamp>.md`

### Flow: Option 2 — Pick a component
1. Show numbered list of all components still using mixins (with mixin names and composable coverage)
2. User picks one by number (or types path directly via CLI)
3. Auto-patch/generate composables for that component's mixins
4. Plan component changes: remove mixin import, remove from `mixins: []`, add composable import, inject `setup()`
5. Show human-readable change list per file
6. `Apply changes? (y/n)`
7. Write files + save diff to `migration-diff-<timestamp>.md`

> Only files related to THIS component are written. Other components sharing the same composable are not touched (composable patches are additive and safe).

### Flow: Option 3 — Pick a mixin
1. Show list of all mixins with component counts and composable status
2. User picks one
3. Patch/generate the composable for that mixin
4. For EVERY component using that mixin: remove mixin import, remove from `mixins: []`, add composable import, inject `setup()`
5. Show human-readable change list per file
6. `Apply changes? This will update X files. (y/n)`
7. Write files + save diff to `migration-diff-<timestamp>.md`

### Flow: Option 4 — Project status
1. Scan entire project (read-only)
2. Generate detailed markdown report:
   - Summary counts (total components, ready, blocked)
   - Mixin overview table (name, component count, composable found/needed)
   - Per-component section (mixins used, status: ready/blocked, reason)
3. Save to `migration-status-<timestamp>.md`
4. Print a concise summary to terminal; show full report path

### Change summary format (terminal)
Instead of a raw unified diff, show a per-file description:
```
  Composable changes:
    src/composables/useTable.js: adding refs: tableData, loading · adding functions: fetchRows · adding to return: tableData, loading, fetchRows

  Component changes:
    src/components/Dashboard.vue: removing mixin imports: tableMixin · adding composable imports: useTable · injecting setup()
```

### Diff file format
Full unified diff written to `migration-diff-<timestamp>.md` with one `## filename` section per changed file containing a fenced `diff` code block.

### CLI direct commands (non-interactive)
| Command | Equivalent |
|---|---|
| `npx vue3-migration` | Interactive menu |
| `npx vue3-migration all` | Full project migration |
| `npx vue3-migration component <path>` | Migrate one component (skip list, go direct) |
| `npx vue3-migration mixin <name>` | Retire one mixin |
| `npx vue3-migration status` | Generate status report |
| `npx vue3-migration --help` | Show help |

---

## Files Changed

| File | Action |
|---|---|
| `vue3_migration/cli.py` | Rewrite menu, dispatch, and all workflow functions |
| `vue3_migration/reporting/diff.py` | Rewrite: human-readable change list + MD diff writer |
| `vue3_migration/reporting/markdown.py` | Add `generate_status_report()` |
| `README.md` | Update for new commands |
| `tests/test_cli_menu.py` | New: menu dispatch tests |
| `tests/test_diff_reporting.py` | New: change summary format tests |
| `tests/test_status_report.py` | New: status report generation tests |

`component_workflow` and `mixin_workflow` remain as modules but are no longer imported or called from `cli.py`.

---

## Task 1: Rewrite `interactive_menu()` and `main()` in `cli.py`

**Files:**
- Modify: `vue3_migration/cli.py`
- Create: `tests/test_cli_menu.py`

**Step 1: Write failing tests**

```python
# tests/test_cli_menu.py
import pytest
from unittest.mock import patch, MagicMock
from vue3_migration.cli import main


def test_menu_shows_four_options(capsys):
    with patch("builtins.input", return_value="q"):
        main([])
    out = capsys.readouterr().out
    assert "Full project" in out
    assert "Pick a component" in out
    assert "Pick a mixin" in out
    assert "Project status" in out


def test_main_dispatches_all():
    with patch("vue3_migration.cli.full_project_migration") as mock:
        main(["all"])
    mock.assert_called_once()


def test_main_dispatches_component():
    with patch("vue3_migration.cli.component_migration") as mock:
        main(["component", "src/components/Foo.vue"])
    mock.assert_called_once()


def test_main_dispatches_mixin():
    with patch("vue3_migration.cli.mixin_migration") as mock:
        main(["mixin", "authMixin"])
    mock.assert_called_once()


def test_main_dispatches_status():
    with patch("vue3_migration.cli.project_status") as mock:
        main(["status"])
    mock.assert_called_once()


def test_main_unknown_command_prints_message(capsys):
    main(["foobar"])
    out = capsys.readouterr().out
    assert "Unknown command" in out
```

**Step 2: Run tests to verify they fail**

```bash
cd c:\Users\eden7\projects\vue3-migration
python -m pytest tests/test_cli_menu.py -v
```

Expected: FAIL — `main()` does not accept a list argument, new functions don't exist yet.

**Step 3: Refactor `main()` to accept an optional `argv` list**

Replace the existing `main()` in `vue3_migration/cli.py`:

```python
def main(argv: list[str] | None = None):
    import sys
    args = argv if argv is not None else sys.argv[1:]
    config = MigrationConfig()

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
```

**Step 4: Rewrite `interactive_menu()`**

Replace the existing `interactive_menu()` in `vue3_migration/cli.py`:

```python
def interactive_menu(config: MigrationConfig):
    print()
    print(f"  {bold('Vue Mixin Migration Tool')}")
    print(f"  {dim('Migrate Vue 2 mixins to Vue 3 composables.')}")
    print()
    print(f"  {bold('1.')} {green('Full project')}")
    print(f"     Migrate every component at once. Auto-patches and generates")
    print(f"     composables as needed. Shows a change summary before writing.\n")
    print(f"  {bold('2.')} {green('Pick a component')}")
    print(f"     Choose one component from a list. Migrate only that component.")
    print(f"     Safe for large projects — low blast radius, easy to test.\n")
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
```

**Step 5: Add `_print_help()`**

```python
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
```

**Step 6: Add stub functions so tests can import them (implementations come in later tasks)**

```python
def full_project_migration(config: MigrationConfig): pass
def component_migration(path: str, config: MigrationConfig): pass
def mixin_migration(name: str, config: MigrationConfig): pass
def pick_component_migration(config: MigrationConfig): pass
def pick_mixin_migration(config: MigrationConfig): pass
def project_status(config: MigrationConfig): pass
```

**Step 7: Run tests**

```bash
python -m pytest tests/test_cli_menu.py -v
```

Expected: All PASS.

**Step 8: Commit**

```bash
git add vue3_migration/cli.py tests/test_cli_menu.py
git commit -m "refactor(cli): rewrite menu and dispatch to 4-option scope model"
```

---

## Task 2: Human-readable change summary (`reporting/diff.py`)

**Files:**
- Modify: `vue3_migration/reporting/diff.py`
- Create: `tests/test_diff_reporting.py`

**Step 1: Write failing tests**

```python
# tests/test_diff_reporting.py
from pathlib import Path
import pytest
from vue3_migration.models import FileChange, MigrationPlan
from vue3_migration.reporting.diff import format_change_list


def _change(path, original, new):
    return FileChange(file_path=Path(path), original_content=original, new_content=new, changes=[])


def test_detects_added_ref():
    original = "export function useTable() {\n  return {}\n}"
    new = "export function useTable() {\n  const tableData = ref([])\n  return { tableData }\n}"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", original, new)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useTable.js" in out
    assert "tableData" in out
    assert "refs" in out


def test_detects_added_function():
    original = "export function useTable() {\n  return {}\n}"
    new = "export function useTable() {\n  function fetchRows() {}\n  return { fetchRows }\n}"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", original, new)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "fetchRows" in out
    assert "function" in out


def test_detects_new_composable_file():
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useAuth.js", "", "export function useAuth() { return {} }")],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useAuth.js" in out
    assert "new file" in out


def test_detects_removed_mixin_import():
    original = "import authMixin from '../mixins/authMixin'\nexport default { mixins: [authMixin] }"
    new = "import { useAuth } from '../composables/useAuth'\nexport default { setup() { const { user } = useAuth(); return { user } } }"
    plan = MigrationPlan(
        component_changes=[_change("src/components/UserProfile.vue", original, new)],
        composable_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "UserProfile.vue" in out
    assert "authMixin" in out


def test_detects_added_composable_import():
    original = "import authMixin from '../mixins/authMixin'\nexport default { mixins: [authMixin] }"
    new = "import { useAuth } from '../composables/useAuth'\nexport default { setup() { return {} } }"
    plan = MigrationPlan(
        component_changes=[_change("src/components/UserProfile.vue", original, new)],
        composable_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useAuth" in out


def test_skips_unchanged_files():
    content = "export function useTable() { return {} }"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", content, content)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useTable.js" not in out
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_diff_reporting.py -v
```

Expected: FAIL — `format_change_list` does not exist or has old signature.

**Step 3: Implement `format_change_list()` in `reporting/diff.py`**

Replace the entire contents of `vue3_migration/reporting/diff.py`:

```python
"""
Human-readable change summaries and markdown diff file generation.
"""
import difflib
import re
from datetime import datetime
from pathlib import Path

from ..models import FileChange, MigrationPlan
from .terminal import bold, dim, green, yellow


# ---------------------------------------------------------------------------
# Composable change analysis
# ---------------------------------------------------------------------------

def _extract_return_keys(source: str) -> list[str]:
    """Extract keys from the last return { ... } statement."""
    m = re.search(r"return\s*\{([^}]*)\}", source, re.DOTALL)
    if not m:
        return []
    return [k.strip().split(":")[0].strip() for k in m.group(1).split(",") if k.strip()]


def _describe_composable_changes(change: FileChange) -> list[str]:
    """Describe what was added to a composable (refs, computed, functions, return keys)."""
    original_lines = set(change.original_content.splitlines())

    added_refs: list[str] = []
    added_computed: list[str] = []
    added_functions: list[str] = []

    for line in change.new_content.splitlines():
        stripped = line.strip()
        if stripped in original_lines:
            continue
        m = re.match(r"const\s+(\w+)\s*=\s*ref\(", stripped)
        if m:
            added_refs.append(m.group(1))
            continue
        m = re.match(r"const\s+(\w+)\s*=\s*computed\(", stripped)
        if m:
            added_computed.append(m.group(1))
            continue
        m = re.match(r"(?:async\s+)?function\s+(\w+)\s*\(", stripped)
        if m:
            added_functions.append(m.group(1))
            continue
        m = re.match(r"const\s+(\w+)\s*=\s*(?:async\s*)?\(", stripped)
        if m:
            added_functions.append(m.group(1))

    orig_return = set(_extract_return_keys(change.original_content))
    new_return = _extract_return_keys(change.new_content)
    added_to_return = [k for k in new_return if k not in orig_return]

    parts = []
    if added_refs:
        parts.append(f"adding refs: {', '.join(added_refs)}")
    if added_computed:
        parts.append(f"adding computed: {', '.join(added_computed)}")
    if added_functions:
        parts.append(f"adding functions: {', '.join(added_functions)}")
    if added_to_return:
        parts.append(f"adding to return: {', '.join(added_to_return)}")
    return parts


# ---------------------------------------------------------------------------
# Component change analysis
# ---------------------------------------------------------------------------

def _describe_component_changes(change: FileChange) -> list[str]:
    """Describe what changed in a component file (mixin removed, composable added, setup injected)."""
    original_line_set = set(change.original_content.splitlines())
    new_line_set = set(change.new_content.splitlines())

    removed_mixin_imports: list[str] = []
    added_composable_imports: list[str] = []

    for line in change.original_content.splitlines():
        if line in new_line_set:
            continue
        m = re.match(r"import\s+(\w+)\s+from\s+['\"].*[Mm]ixin", line.strip())
        if m:
            removed_mixin_imports.append(m.group(1))

    for line in change.new_content.splitlines():
        if line in original_line_set:
            continue
        m = re.match(r"import\s*\{([^}]+)\}\s*from\s+['\"].*composables?", line.strip(), re.IGNORECASE)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if n.strip()]
            added_composable_imports.extend(names)

    setup_injected = (
        "setup()" in change.new_content and "setup()" not in change.original_content
    )

    parts = []
    if removed_mixin_imports:
        parts.append(f"removing mixin imports: {', '.join(removed_mixin_imports)}")
    if added_composable_imports:
        parts.append(f"adding composable imports: {', '.join(added_composable_imports)}")
    if setup_injected:
        parts.append("injecting setup()")
    return parts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_change_list(plan: MigrationPlan, project_root: Path) -> str:
    """Return a human-readable terminal string describing all planned changes per file."""
    lines: list[str] = []

    composable_changes = [c for c in plan.composable_changes if c.has_changes]
    component_changes = [c for c in plan.component_changes if c.has_changes]

    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    if composable_changes:
        lines.append(f"  {bold('Composable changes:')}")
        for change in composable_changes:
            is_new = not change.original_content.strip()
            parts = ["new file generated"] if is_new else _describe_composable_changes(change)
            desc = " · ".join(parts) if parts else "modified"
            lines.append(f"    {green(_rel(change.file_path))}: {desc}")

    if component_changes:
        lines.append(f"  {bold('Component changes:')}")
        for change in component_changes:
            parts = _describe_component_changes(change)
            desc = " · ".join(parts) if parts else "modified"
            lines.append(f"    {green(_rel(change.file_path))}: {desc}")

    return "\n".join(lines)


def write_diff_report(plan: MigrationPlan, project_root: Path) -> Path:
    """Write a full unified diff to a markdown file. Returns the file path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = project_root / f"migration-diff-{timestamp}.md"

    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    sections: list[str] = [
        "# Migration Diff Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    all_changes = [c for c in (plan.composable_changes + plan.component_changes) if c.has_changes]

    for change in all_changes:
        rel = _rel(change.file_path)
        sections.append(f"## `{rel}`")
        sections.append("")
        if not change.original_content.strip():
            sections.append("**New file**")
            sections.append("")
            sections.append("```javascript")
            sections.append(change.new_content.rstrip())
            sections.append("```")
        else:
            diff_lines = difflib.unified_diff(
                change.original_content.splitlines(keepends=True),
                change.new_content.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            sections.append("```diff")
            sections.append("".join(diff_lines).rstrip())
            sections.append("```")
        sections.append("")

    report_path.write_text("\n".join(sections), encoding="utf-8")
    return report_path
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_diff_reporting.py -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add vue3_migration/reporting/diff.py tests/test_diff_reporting.py
git commit -m "feat(reporting): human-readable change list and markdown diff writer"
```

---

## Task 3: Project status report (`reporting/markdown.py`)

**Files:**
- Modify: `vue3_migration/reporting/markdown.py`
- Create: `tests/test_status_report.py`

**Step 1: Write failing tests**

```python
# tests/test_status_report.py
import os
import pytest
from pathlib import Path
from vue3_migration.models import MigrationConfig
from vue3_migration.reporting.markdown import generate_status_report


@pytest.fixture
def dummy_project(tmp_path):
    """Minimal project: one component using authMixin, one composable useAuth."""
    (tmp_path / "src" / "mixins").mkdir(parents=True)
    (tmp_path / "src" / "composables").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)

    (tmp_path / "src" / "mixins" / "authMixin.js").write_text(
        "export default { data() { return { user: null } }, methods: { logout() {} } }"
    )
    (tmp_path / "src" / "composables" / "useAuth.js").write_text(
        "export function useAuth() { const user = ref(null); function logout() {} return { user, logout } }"
    )
    (tmp_path / "src" / "components" / "UserProfile.vue").write_text(
        "import authMixin from '../mixins/authMixin'\nexport default { mixins: [authMixin] }"
    )
    return tmp_path


def test_status_report_contains_summary(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "## Summary" in report
    assert "Components with mixins remaining" in report


def test_status_report_lists_mixin(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "authMixin" in report


def test_status_report_lists_component(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "UserProfile.vue" in report


def test_status_report_mixin_table_has_composable_status(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "found" in report or "needs generation" in report
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_status_report.py -v
```

Expected: FAIL — `generate_status_report` does not exist yet.

**Step 3: Add `generate_status_report()` to `reporting/markdown.py`**

Append to the end of `vue3_migration/reporting/markdown.py`:

```python
def generate_status_report(project_root: Path, config) -> str:
    """Generate a detailed markdown status report of migration progress."""
    import os
    from collections import Counter
    from datetime import datetime

    from ..core.component_analyzer import parse_imports, parse_mixins_array
    from ..core.composable_search import (
        collect_composable_stems,
        find_composable_dirs,
        mixin_has_composable,
    )
    from ..core.file_resolver import resolve_mixin_stem

    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs)
    mixin_counter: Counter[str] = Counter()
    components_info: list[dict] = []

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
            mixin_names = parse_mixins_array(source)
            if not mixin_names:
                continue
            imports = parse_imports(source)
            stems = []
            for name in mixin_names:
                imp = imports.get(name, "")
                stems.append(resolve_mixin_stem(imp) if imp else name)
                mixin_counter[stems[-1]] += 1
            covered = sum(1 for s in stems if mixin_has_composable(s, composable_stems))
            try:
                rel = filepath.relative_to(project_root)
            except ValueError:
                rel = filepath
            components_info.append(
                {
                    "rel_path": rel,
                    "stems": stems,
                    "covered": covered,
                    "total": len(stems),
                    "all_covered": covered == len(stems),
                }
            )

    ready = sum(1 for c in components_info if c["all_covered"])
    blocked = len(components_info) - ready

    lines: list[str] = [
        "# Vue Migration Status Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Components with mixins remaining: **{len(components_info)}**",
        f"- Ready to migrate now: **{ready}**",
        f"- Blocked (composable missing or incomplete): **{blocked}**",
        "",
        "## Mixin Overview",
        "",
        "| Mixin | Used in | Composable |",
        "|-------|---------|------------|",
    ]

    for stem, count in mixin_counter.most_common():
        has_comp = mixin_has_composable(stem, composable_stems)
        status = "✓ found" if has_comp else "needs generation"
        lines.append(f"| {stem} | {count} | {status} |")

    lines += ["", "## Components", ""]

    # Ready components first, then blocked; alphabetical within each group
    components_info.sort(key=lambda c: (not c["all_covered"], str(c["rel_path"])))

    for comp in components_info:
        if comp["all_covered"]:
            status_str = "**Ready** — all composables found"
        else:
            missing = comp["total"] - comp["covered"]
            status_str = f"**Blocked** — {missing} composable(s) missing or incomplete"

        lines.append(f"### `{comp['rel_path']}`")
        lines.append(f"- Mixins: {', '.join(f'`{s}`' for s in comp['stems'])}")
        lines.append(f"- Status: {status_str}")
        lines.append("")

    return "\n".join(lines)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_status_report.py -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add vue3_migration/reporting/markdown.py tests/test_status_report.py
git commit -m "feat(reporting): add generate_status_report() for project overview markdown"
```

---

## Task 4: Implement `full_project_migration()` in `cli.py`

**Files:**
- Modify: `vue3_migration/cli.py`

**Step 1: Replace the `full_project_migration` stub with the real implementation**

This reuses the existing `auto_migrate_workflow.run()` engine, wires in the new summary/diff functions, and writes files on confirmation.

Add shared helpers first (used by all three migration workflows):

```python
# --- Shared migration helpers ---

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
                label = green("CREATED") if is_new else green("PATCHED ")
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
```

Then implement `full_project_migration()`:

```python
def full_project_migration(config: MigrationConfig) -> None:
    from .workflows import auto_migrate_workflow

    print(f"\n{bold('Full project migration')}")
    print(f"  {dim('Scan → patch composables → inject setup() → confirm → write')}\n")

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
```

**Step 2: Run existing integration tests to confirm nothing broke**

```bash
python -m pytest tests/test_integration_auto_migrate.py -v
```

Expected: PASS (the engine is unchanged, only the CLI wrapper changed).

**Step 3: Commit**

```bash
git add vue3_migration/cli.py
git commit -m "feat(cli): implement full_project_migration() with new summary/diff format"
```

---

## Task 5: Implement `pick_component_migration()` and `component_migration()`

**Files:**
- Modify: `vue3_migration/cli.py`

**Step 1: Add `_scan_components_with_mixins()` helper**

Extract scanning logic (no printing) into a reusable helper:

```python
def _scan_components_with_mixins(project_root: Path, config: MigrationConfig) -> list[dict]:
    """Return list of component info dicts for all .vue files that use mixins."""
    from .core.composable_search import collect_composable_stems, find_composable_dirs, mixin_has_composable

    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs)
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
            results.append(
                {
                    "rel_path": rel,
                    "abs_path": filepath,
                    "mixin_names": mixin_names,
                    "mixin_stems": stems,
                    "covered": covered,
                    "total": len(stems),
                }
            )

    results.sort(key=lambda c: -len(c["mixin_names"]))
    return results
```

**Step 2: Implement `pick_component_migration()` (interactive list)**

```python
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
        print(f"     {dim(', '.join(comp['mixin_stems']))}  —  {cov_str}")

    print(f"\n  Enter a number (1-{len(components)}) or {bold('q')} to go back.\n")
    choice = input("  > ").strip()

    if not choice or choice.lower() == "q":
        return
    try:
        idx = int(choice)
        if not (1 <= idx <= len(components)):
            print(f"  {yellow('Number out of range.')}")
            return
    except ValueError:
        print(f"  {yellow('Please enter a number.')}")
        return

    comp = components[idx - 1]
    print(f"\n{bold('Migrating:')} {green(str(comp['rel_path']))}\n")
    _run_component_migration(comp["abs_path"], config)
```

**Step 3: Implement `component_migration()` (direct path, used by CLI command)**

```python
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
```

**Step 4: Implement shared `_run_component_migration()`**

```python
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
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_cli_menu.py tests/test_integration_auto_migrate.py -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add vue3_migration/cli.py
git commit -m "feat(cli): implement pick_component_migration() and component_migration()"
```

---

## Task 6: Implement `pick_mixin_migration()` and `mixin_migration()`

**Files:**
- Modify: `vue3_migration/cli.py`

**Step 1: Add `_scan_mixin_usage()` helper**

```python
def _scan_mixin_usage(project_root: Path, config: MigrationConfig) -> list[dict]:
    """Return list of mixin info dicts sorted by usage count."""
    from collections import Counter
    from .core.composable_search import collect_composable_stems, find_composable_dirs, mixin_has_composable

    composable_dirs = find_composable_dirs(project_root)
    composable_stems = collect_composable_stems(composable_dirs)
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
```

**Step 2: Implement `pick_mixin_migration()` (interactive list)**

```python
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

    print(f"\n  Enter a number (1-{len(mixins)}) or {bold('q')} to go back.\n")
    choice = input("  > ").strip()

    if not choice or choice.lower() == "q":
        return
    try:
        idx = int(choice)
        if not (1 <= idx <= len(mixins)):
            print(f"  {yellow('Number out of range.')}")
            return
    except ValueError:
        print(f"  {yellow('Please enter a number.')}")
        return

    mixin = mixins[idx - 1]
    component_word = "component" if mixin["count"] == 1 else "components"
    print(f"\n{bold('Retiring:')} {green(mixin['stem'])} across {yellow(str(mixin['count']))} {component_word}\n")
    _run_mixin_migration(mixin["stem"], config)
```

**Step 3: Implement `mixin_migration()` (direct name, used by CLI command)**

```python
def mixin_migration(name: str, config: MigrationConfig) -> None:
    # Strip file extension and path separators if user passed a path
    stem = Path(name).stem
    print(f"\n{bold('Retiring mixin:')} {green(stem)}\n")
    _run_mixin_migration(stem, config)
```

**Step 4: Implement shared `_run_mixin_migration()`**

```python
def _run_mixin_migration(mixin_stem: str, config: MigrationConfig) -> None:
    from .workflows import auto_migrate_workflow

    plan = auto_migrate_workflow.run_scoped(
        config.project_root, config, mixin_stem=mixin_stem
    )

    if not plan.has_changes:
        print(f"  {green('Nothing to migrate.')} No ready components found for this mixin.")
        return

    component_count = sum(1 for c in plan.component_changes if c.has_changes)
    component_word = "component" if component_count == 1 else "components"
    print(f"  This will update {yellow(str(component_count))} {component_word}.\n")

    _show_change_summary(plan, config.project_root)

    answer = input(f"\n{bold('Apply changes?')} (y/n): ").strip().lower()
    if answer != "y":
        print("  Aborted. No files were written.")
        return

    _apply_plan(plan, config.project_root)
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_cli_menu.py -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add vue3_migration/cli.py
git commit -m "feat(cli): implement pick_mixin_migration() and mixin_migration()"
```

---

## Task 7: Implement `project_status()`

**Files:**
- Modify: `vue3_migration/cli.py`

**Step 1: Replace the `project_status` stub**

```python
def project_status(config: MigrationConfig) -> None:
    from .reporting.markdown import generate_status_report
    from datetime import datetime

    print(f"\n{bold('Project status')}")
    print(f"  {dim('Scanning project...')}\n")

    report = generate_status_report(config.project_root, config)

    # Print concise terminal summary (first ~15 lines = summary + mixin table header)
    for line in report.splitlines()[:20]:
        print(f"  {line}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = config.project_root / f"migration-status-{timestamp}.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n  {bold('Full report saved to:')} {green(report_path.name)}")
```

**Step 2: Run tests**

```bash
python -m pytest tests/test_status_report.py tests/test_cli_menu.py -v
```

Expected: All PASS.

**Step 3: Commit**

```bash
git add vue3_migration/cli.py
git commit -m "feat(cli): implement project_status() with markdown report output"
```

---

## Task 8: Remove old CLI functions and dead imports

**Files:**
- Modify: `vue3_migration/cli.py`

**Step 1: Delete these functions from `cli.py`**

- `scan_project()` — replaced by `_scan_components_with_mixins()` + `pick_component_migration()`
- `auto_migrate()` — replaced by `full_project_migration()`
- `auto_migrate_scoped()` — replaced by `_run_component_migration()` / `_run_mixin_migration()`

**Step 2: Remove these imports from `cli.py`**

```python
# Remove these lines:
from .workflows import component_workflow, mixin_workflow
```

**Step 3: Run full test suite**

```bash
python -m pytest tests/ -v
```

If any existing tests import or call the removed functions, update them to use the new equivalents. The integration tests that test `auto_migrate_workflow` directly should still pass unchanged.

**Step 4: Commit**

```bash
git add vue3_migration/cli.py
git commit -m "refactor(cli): remove old scan_project, auto_migrate, auto_migrate_scoped functions"
```

---

## Task 9: Update README

**Files:**
- Modify: `README.md`

Replace the entire README content:

```markdown
# vue3-migration

A CLI tool that migrates Vue 2 mixins to Vue 3 composables.

## Requirements

- Node.js >= 14
- Python >= 3.9

## Installation

```bash
npm install -D vue3-migration
```

## Usage

Run from the root of your Vue project:

```bash
npx vue3-migration
```

This opens an interactive menu with four options:

| # | Option | Description |
|---|--------|-------------|
| 1 | **Full project** | Migrate every component at once. Auto-patches and generates composables as needed. Shows a per-file change summary and requires confirmation before writing. |
| 2 | **Pick a component** | Choose one component from a list. Migrate only that file. Safe for large projects — low blast radius, easy to test and review. |
| 3 | **Pick a mixin** | Fully retire one mixin. Patches/generates its composable and updates every component that uses it. |
| 4 | **Project status** | Read-only. Generates a detailed markdown report of what's migrated, what's ready, and what's blocked. No files are changed. |

### Direct commands

```bash
npx vue3-migration all                               # Migrate entire project
npx vue3-migration component src/components/Foo.vue # Migrate one component
npx vue3-migration mixin authMixin                  # Retire one mixin
npx vue3-migration status                            # Generate status report
```

### Output files

Every migration writes a `migration-diff-<timestamp>.md` with a full before/after diff of every changed file.

`npx vue3-migration status` writes a `migration-status-<timestamp>.md` with:
- Summary counts (total, ready, blocked)
- Mixin overview table
- Per-component status and blocking reason

## Workflow for large projects

For large codebases where each change is critical:

1. Run `npx vue3-migration status` to see the full picture.
2. Use **Pick a component** (option 2) to migrate one component at a time.
3. Test after each migration, then move on to the next.
4. When a mixin is used everywhere and you're ready to retire it fully, use **Pick a mixin** (option 3).
```

**Step: Commit**

```bash
git add README.md
git commit -m "docs: update README for new 4-option UX and direct commands"
```

---

## Task 10: End-to-end smoke test

**Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All PASS.

**Step 2: Smoke test the interactive menu manually**

```bash
python -m vue3_migration
```

- Verify menu shows 4 options with correct descriptions
- Choose option 4 (status) → verify `.md` report is created in project root
- Choose option 2 (component) → verify numbered list appears, choose one, see change summary, enter `n` to abort
- Choose option 3 (mixin) → verify mixin table appears, choose one, see change summary, enter `n` to abort
- Choose option 1 (full project) → verify change summary appears, enter `n` to abort

**Step 3: Smoke test direct commands**

```bash
python -m vue3_migration --help
python -m vue3_migration status
python -m vue3_migration component src/components/SomeComponent.vue
```

**Step 4: Final commit**

```bash
git add .
git commit -m "test: end-to-end smoke test pass for new UX"
```

---

## Summary of all commits

1. `refactor(cli): rewrite menu and dispatch to 4-option scope model`
2. `feat(reporting): human-readable change list and markdown diff writer`
3. `feat(reporting): add generate_status_report() for project overview markdown`
4. `feat(cli): implement full_project_migration() with new summary/diff format`
5. `feat(cli): implement pick_component_migration() and component_migration()`
6. `feat(cli): implement pick_mixin_migration() and mixin_migration()`
7. `feat(cli): implement project_status() with markdown report output`
8. `refactor(cli): remove old scan_project, auto_migrate, auto_migrate_scoped functions`
9. `docs: update README for new 4-option UX and direct commands`
