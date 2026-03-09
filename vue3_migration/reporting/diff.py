"""
Human-readable change summaries and markdown diff file generation.
"""
import difflib
import re
from datetime import datetime
from pathlib import Path

from ..models import FileChange, MigrationPlan
from .markdown import build_action_plan, build_recipes_section
from .terminal import bold, dim, green


# ---------------------------------------------------------------------------
# Low-level diff utility (kept for backward compatibility)
# ---------------------------------------------------------------------------

def build_unified_diff(original: str, modified: str, path: str) -> str:
    """Generate a unified diff string between original and modified content.

    Returns an empty string if there are no changes.
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


# ---------------------------------------------------------------------------
# Composable change analysis
# ---------------------------------------------------------------------------

def _extract_return_keys(source: str) -> list[str]:
    """Extract keys from the last return { ... } statement."""
    matches = re.findall(r"return\s*\{([^}]*)\}", source, re.DOTALL)
    if not matches:
        return []
    return [k.strip().split(":")[0].strip() for k in matches[-1].split(",") if k.strip()]


def _describe_composable_changes(change: FileChange) -> list[str]:
    """Describe what was added to a composable (refs, computed, functions, return keys).

    Returns a list of individual detail lines (one item per line).
    """
    original_lines = {line.strip() for line in change.original_content.splitlines()}

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
        parts.append(f"+ refs: {', '.join(added_refs)}")
    if added_computed:
        parts.append(f"+ computed: {', '.join(added_computed)}")
    if added_functions:
        parts.append(f"+ functions: {', '.join(added_functions)}")
    if added_to_return:
        parts.append(f"+ return: {', '.join(added_to_return)}")
    return parts


# ---------------------------------------------------------------------------
# Component change analysis
# ---------------------------------------------------------------------------

def _describe_component_changes(change: FileChange) -> list[str]:
    """Describe what changed in a component file (mixin removed, composable added, setup injected).

    Returns a list of individual detail lines (one item per line).
    """
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
        parts.append(f"- mixins: {', '.join(removed_mixin_imports)}")
    if added_composable_imports:
        parts.append(f"+ composables: {', '.join(added_composable_imports)}")
    if setup_injected:
        parts.append("+ setup() injected")
    return parts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_change_list(plan: MigrationPlan, project_root: Path) -> str:
    """Return a human-readable terminal string describing all planned changes per file."""
    lines: list[str] = []

    composable_changes = [c for c in plan.composable_changes if c.has_changes]
    component_changes = [c for c in plan.component_changes if c.has_changes]

    if composable_changes:
        lines.append(f"  {bold('Composable changes:')}")
        for change in composable_changes:
            is_new = not change.original_content.strip()
            lines.append(f"    {green(change.file_path.name)}")
            if is_new:
                lines.append(f"      {dim('new file generated')}")
            else:
                for part in _describe_composable_changes(change):
                    lines.append(f"      {dim(part)}")

    if composable_changes and component_changes:
        lines.append("")

    if component_changes:
        lines.append(f"  {bold('Component changes:')}")
        for change in component_changes:
            parts = _describe_component_changes(change)
            lines.append(f"    {green(change.file_path.name)}")
            for part in parts:
                lines.append(f"      {dim(part)}")

    return "\n".join(lines)


def write_migration_report(plan: MigrationPlan, project_root: Path) -> Path:
    """Write a migration report with recipes + action plan. Returns the file path."""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    report_path = project_root / f"migration-report-{timestamp}.md"

    # Count totals for header
    all_changes = [c for c in (plan.composable_changes + plan.component_changes) if c.has_changes]
    _header_parts = [f"{len(all_changes)} file{'s' if len(all_changes) != 1 else ''}"]
    if plan.entries_by_component:
        _seen: set[str] = set()
        _all_w = []
        for _cp2, _el2 in plan.entries_by_component:
            for _e2 in _el2:
                if _e2.mixin_stem not in _seen:
                    _seen.add(_e2.mixin_stem)
                    _all_w.extend(_e2.warnings)
        _ec = sum(1 for w in _all_w if w.severity == "error")
        _wc = sum(1 for w in _all_w if w.severity == "warning")
        _ic = sum(1 for w in _all_w if w.severity == "info")
        if _ec:
            _header_parts.append(f"{_ec} error{'s' if _ec != 1 else ''}")
        if _wc:
            _header_parts.append(f"{_wc} warning{'s' if _wc != 1 else ''}")
        if _ic:
            _header_parts.append(f"{_ic} info")

    sections: list[str] = [
        "# Migration Report",
        "",
        f"`{now.strftime('%Y-%m-%d %H:%M:%S')}` \u2014 {' \u00b7 '.join(_header_parts)}",
        "",
        "> Use `git diff` to review the actual code changes.",
        "",
        "---",
        "",
    ]

    if plan.entries_by_component:
        # Section 1: Migration Recipes
        recipes = build_recipes_section(plan.entries_by_component)
        if recipes:
            sections.append(recipes)
            sections.append("")

        # Section 2: Action Plan
        action_plan = build_action_plan(
            plan.entries_by_component, plan.composable_changes, project_root
        )
        if action_plan:
            sections.append(action_plan)
            sections.append("")

    report_path.write_text("\n".join(sections), encoding="utf-8")
    return report_path


# Backward-compatible alias
write_diff_report = write_migration_report


# ---------------------------------------------------------------------------
# Legacy (kept until Task 8 removes it)
# ---------------------------------------------------------------------------

def print_diff_summary(changes, project_root: Path) -> None:
    """Legacy function — replaced by format_change_list + write_diff_report."""
    pass
