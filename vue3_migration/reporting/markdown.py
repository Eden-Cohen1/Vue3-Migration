"""
Markdown report generation for migration analysis results.
"""

from pathlib import Path

from ..models import ConfidenceLevel, FileChange, MigrationWarning, MixinEntry
from .terminal import md_green, md_yellow

_SKIPPED_CATEGORIES = frozenset({
    "skipped-all-overridden",
    "skipped-lifecycle-only",
    "skipped-no-usage",
})


def build_component_report(
    component_path: Path,
    mixin_entries: list[MixinEntry],
    project_root: Path,
) -> str:
    """Build a markdown migration report for a single component."""
    lines: list[str] = []
    w = lines.append

    try:
        component_rel = component_path.relative_to(project_root)
    except ValueError:
        component_rel = component_path

    w(f"# Migration Report: {md_green(str(component_rel))}\n")

    ready_entries = []
    blocked_entries = []

    for entry in mixin_entries:
        mixin_name = entry.mixin_stem
        w(f"## Mixin: {mixin_name}\n")
        w(f"**File:** {md_green(str(entry.mixin_path))}\n")

        # Members breakdown
        for section in ("data", "computed", "methods"):
            section_members = getattr(entry.members, section)
            if section_members:
                w(f"**{section}:** {', '.join(section_members)}\n")

        # Lifecycle hooks
        if entry.lifecycle_hooks:
            w(f"\n**Lifecycle hooks:** {', '.join(entry.lifecycle_hooks)}")
            w("> Must be manually migrated (e.g. `mounted` -> `onMounted`).\n")

        # Used members
        used = entry.used_members
        w(f"\n**Used by component:** {', '.join(used) if used else 'none detected'}\n")

        # Composable analysis
        comp = entry.composable
        cls = entry.classification

        if not entry.used_members:
            w("**Status: READY** -- no members used, mixin can be safely removed.\n")
            ready_entries.append(entry)
        elif not comp or not cls:
            w(f"**Composable:** {md_yellow('NOT FOUND')}\n")
            blocked_entries.append(entry)
        else:
            w(f"**Composable:** {md_green(str(comp.file_path))}")
            w(f"**Function:** `{comp.fn_name}`")
            w(f"**Import path:** `{comp.import_path}`")
            w(f"> {md_yellow('Verify the above path and function name are correct.')}\n")

            if cls.truly_missing:
                w(f"**MISSING from composable:** {', '.join(cls.truly_missing)}\n")
            if cls.overridden:
                w(f"**Overridden by component:** {', '.join(cls.overridden)}")
                w("> These mixin members are redefined in the component itself, "
                  "so the composable doesn't need to provide them.\n")

            if cls.truly_not_returned:
                w(f"**NOT in return statement:** {', '.join(cls.truly_not_returned)}")
                w("> These exist in the composable but are not returned, "
                  "so the component cannot access them.\n")
            if cls.overridden_not_returned:
                w(f"**Overridden (not returned):** {', '.join(cls.overridden_not_returned)}")
                w("> Not returned by composable, but the component defines them itself.\n")

            if cls.is_ready:
                status_note = ""
                override_count = len(cls.overridden) + len(cls.overridden_not_returned)
                if override_count:
                    status_note = f" ({override_count} member(s) overridden by component)"
                w(f"**Status: READY**{status_note} -- all needed members are present and returned.\n")
                ready_entries.append(entry)
            else:
                blocked_entries.append(entry)

        w("---\n")

    # --- Actionable Summary ---
    w("\n## Action Items\n")

    if blocked_entries:
        for entry in blocked_entries:
            mixin_name = entry.mixin_stem
            comp = entry.composable
            cls = entry.classification

            if not comp:
                w(f"### {mixin_name}: Create composable")
                w(f"- {md_yellow('A composable needs to be created')} for `{mixin_name}`.")
                if entry.used_members:
                    w(f"- It must expose: {', '.join(entry.used_members)}\n")
            else:
                w(f"### {mixin_name}: Update `{comp.fn_name}`")
                if cls and cls.missing:
                    w(f"- Add to composable: {', '.join(cls.missing)}")
                if cls and cls.not_returned:
                    w(f"- Add to return statement: {', '.join(cls.not_returned)}")
                w(f"- File: {md_green(str(comp.file_path))}\n")

    if ready_entries:
        w("### Ready for injection")
        for entry in ready_entries:
            if not entry.used_members:
                w(f"- `{entry.mixin_stem}` -- no members used, will just remove mixin")
            else:
                comp = entry.composable
                w(f"- `{entry.mixin_stem}` -> `{comp.fn_name}` ({len(entry.used_members)} members)")
        w("")

    if not blocked_entries:
        w("All mixins are ready. Run the script again to inject.\n")
    elif ready_entries:
        w(f"{len(ready_entries)} of {len(mixin_entries)} mixin(s) are ready for partial injection.\n")
    else:
        w(f"{md_yellow('No mixins are ready for injection yet.')} Fix the issues above and re-run.\n")

    return "\n".join(lines)


def generate_status_report(project_root: Path, config) -> str:
    """Generate a detailed markdown status report of migration progress."""
    import os
    import re as _re
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
    composable_stems = collect_composable_stems(composable_dirs, project_root=project_root)

    # Detect composables that need manual migration (reactive() or variable return)
    manual_stems: set[str] = set()
    for comp_dir in composable_dirs:
        for dirpath_c, _, filenames_c in os.walk(comp_dir):
            for fn_c in filenames_c:
                fp = Path(dirpath_c) / fn_c
                if fp.suffix not in (".js", ".ts") or not fp.stem.lower().startswith("use"):
                    continue
                try:
                    content = fp.read_text(errors="ignore")
                except Exception:
                    continue
                if 'reactive(' in content or not _re.search(r'\breturn\s*\{', content):
                    manual_stems.add(fp.stem.lower())

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
            covered = sum(
                1 for s in stems
                if mixin_has_composable(s, composable_stems)
                and not mixin_has_composable(s, manual_stems)
            )
            needs_manual = sum(
                1 for s in stems
                if mixin_has_composable(s, manual_stems)
            )
            try:
                rel = filepath.relative_to(project_root)
            except ValueError:
                rel = filepath
            components_info.append(
                {
                    "rel_path": rel,
                    "stems": stems,
                    "covered": covered,
                    "needs_manual": needs_manual,
                    "total": len(stems),
                    "all_covered": covered == len(stems) and needs_manual == 0,
                    "has_manual": needs_manual > 0,
                }
            )

    ready = sum(1 for c in components_info if c["all_covered"])
    needs_manual_count = sum(1 for c in components_info if c["has_manual"])
    blocked = len(components_info) - ready - needs_manual_count

    lines: list[str] = [
        "# Vue Migration Status Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- Components with mixins remaining: **{len(components_info)}**",
        f"- Ready to migrate now: **{ready}**",
    ]
    if needs_manual_count:
        lines.append(f"- Needs manual migration: **{needs_manual_count}**")
    lines.extend([
        f"- Blocked (composable missing or incomplete): **{blocked}**",
        "",
        "## Mixin Overview",
        "",
        "| Mixin | Used in | Composable |",
        "|-------|---------|------------|",
    ])

    for stem, count in mixin_counter.most_common():
        has_comp = mixin_has_composable(stem, composable_stems)
        is_manual = mixin_has_composable(stem, manual_stems)
        if is_manual:
            status = "found (needs manual migration)"
        elif has_comp:
            status = "found"
        else:
            status = "needs generation"
        lines.append(f"| {stem} | {count} | {status} |")

    lines += ["", "## Components", ""]

    # Ready first, then needs-manual, then blocked; alphabetical within each group
    components_info.sort(key=lambda c: (
        0 if c["all_covered"] else (1 if c["has_manual"] else 2),
        str(c["rel_path"]),
    ))

    for comp in components_info:
        if comp["all_covered"]:
            status_str = "**Ready** -- all composables found"
        elif comp["has_manual"]:
            status_str = "**Needs manual migration** -- composable uses reactive() or variable return"
        else:
            missing = comp["total"] - comp["covered"] - comp["needs_manual"]
            status_str = f"**Blocked** -- {missing} composable(s) missing or incomplete"

        lines.append(f"### `{comp['rel_path']}`")
        lines.append(f"- Mixins: {', '.join(f'`{s}`' for s in comp['stems'])}")
        lines.append(f"- Status: {status_str}")
        lines.append("")

    return "\n".join(lines)


def build_audit_report(
    mixin_path: Path,
    members: dict[str, list[str]],
    lifecycle_hooks: list[str],
    importing_files: list[Path],
    all_member_names: list[str],
    composable_path_arg: str | None,
    composable_identifiers: list[str],
    composable_exists: bool,
    project_root: Path,
    usage_map: dict[str, list[str]],
) -> str:
    """Build a markdown audit report for a single mixin."""
    lines: list[str] = []
    w = lines.append

    w(f"# Mixin Audit: {mixin_path.name}\n")

    w("## Mixin Members\n")
    for section in ("data", "computed", "methods"):
        if members[section]:
            w(f"**{section}:** {', '.join(members[section])}\n")

    w("\n## Lifecycle Hooks\n")
    if lifecycle_hooks:
        w(f"{', '.join(lifecycle_hooks)}\n")
        w("\n> These hooks contain logic that must be manually migrated "
          "to the composable (e.g. `mounted` -> `onMounted`).\n")
    else:
        w("*No lifecycle hooks found in this mixin.*\n")

    w(f"\n## Files Importing the Mixin ({len(importing_files)})\n")

    for file_path in sorted(importing_files):
        relative_path = file_path.relative_to(project_root)
        used = usage_map.get(str(relative_path), [])
        w(f"### {relative_path}\n")
        if used:
            w(f"Uses: {', '.join(used)}\n")
        else:
            w("Uses: *(none detected -- mixin may be unused here)*\n")

    all_used_members = sorted(set(
        member for used_list in usage_map.values() for member in used_list
    ))

    w("\n## Composable Status\n")
    if not composable_path_arg:
        w("**No composable path provided.** A composable should be created.\n")
    elif not composable_exists:
        w(f"**Composable file not found at `{composable_path_arg}`.** It should be created.\n")
    else:
        missing = [m for m in all_used_members if m not in composable_identifiers]
        if missing:
            w(f"**Missing from composable:** {', '.join(missing)}\n")
        else:
            w("All used members are present in the composable.\n")

    w("\n## Summary\n")
    w(f"- Total mixin members: {len(all_member_names)}\n")
    w(f"- Lifecycle hooks: {len(lifecycle_hooks)}\n")
    w(f"- Members used across codebase: {len(all_used_members)}\n")

    unused_members = [m for m in all_member_names if m not in all_used_members]
    if unused_members:
        w(f"- Unused members (candidates for removal): {', '.join(unused_members)}\n")

    return "\n".join(lines)


def build_per_component_index(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
    confidence_map: dict[str, ConfidenceLevel],
    project_root: Path,
) -> str:
    """Build a per-component quick-reference index."""
    if not entries_by_component:
        return ""

    _CONF_ICON = {ConfidenceLevel.LOW: "\u274c", ConfidenceLevel.MEDIUM: "\u26a0\ufe0f", ConfidenceLevel.HIGH: "\u2705"}

    lines: list[str] = []
    a = lines.append
    a("## Per-Component Guide\n")

    for comp_path, entry_list in entries_by_component:
        try:
            comp_rel = comp_path.relative_to(project_root)
        except ValueError:
            comp_rel = comp_path
        a(f"### {comp_rel.name}\n")

        for entry in entry_list:
            entry_cats = {w.category for w in entry.warnings}
            is_skipped = entry_cats and entry_cats <= _SKIPPED_CATEGORIES

            if is_skipped:
                reason = entry.warnings[0].message if entry.warnings else "skipped"
                a(f"- \u2139\ufe0f **{entry.mixin_stem}** skipped \u2014 {reason}")
            elif entry.composable:
                conf = confidence_map.get(entry.mixin_stem, ConfidenceLevel.HIGH)
                icon = _CONF_ICON.get(conf, "\u2753")
                error_count = sum(1 for w in entry.warnings if w.severity == "error")
                warn_count = sum(1 for w in entry.warnings if w.severity == "warning")
                if error_count or warn_count:
                    parts = []
                    if error_count:
                        parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
                    if warn_count:
                        parts.append(f"{warn_count} warning{'s' if warn_count != 1 else ''}")
                    detail = ", ".join(parts)
                    a(f"- {icon} **{entry.composable.fn_name}** ({conf.value}) \u2014 {detail} \u2192 [See warnings](#{entry.mixin_stem})")
                else:
                    a(f"- {icon} **{entry.composable.fn_name}** ({conf.value}) \u2014 No issues")
            else:
                a(f"- \u274c **{entry.mixin_stem}** \u2014 composable not found")

        a("")

    return "\n".join(lines)


def build_warning_summary(
    entries_by_component: "list[tuple[Path, list[MixinEntry]]]",
    composable_changes: "list[FileChange] | None" = None,
) -> str:
    """Build a markdown Migration Summary checklist for the diff report.

    Groups warnings by mixin/composable with confidence levels, severity
    icons, and actionable checkboxes. De-duplicates entries that share the
    same mixin_stem (a mixin used by multiple components).
    """
    from ..core.warning_collector import compute_confidence

    # De-duplicate entries by mixin_stem (keep first occurrence)
    seen_stems: set[str] = set()
    unique_entries: list[MixinEntry] = []
    for _comp_path, entry_list in entries_by_component:
        for entry in entry_list:
            if entry.mixin_stem not in seen_stems:
                seen_stems.add(entry.mixin_stem)
                unique_entries.append(entry)

    if not unique_entries:
        return ""

    # Separate skipped entries from active entries
    skipped_rows: list[tuple[str, str, str]] = []  # (component, mixin, reason)
    active_entries: list[MixinEntry] = []

    for entry in unique_entries:
        entry_cats = {w.category for w in entry.warnings}
        if entry_cats and entry_cats <= _SKIPPED_CATEGORIES:
            # Find which component(s) this mixin was used in
            for comp_path, entry_list in entries_by_component:
                for e in entry_list:
                    if e.mixin_stem == entry.mixin_stem:
                        reason = entry.warnings[0].message.split(":", 1)[-1].strip() if entry.warnings else "unknown"
                        comp_name = comp_path.name
                        skipped_rows.append((comp_name, entry.mixin_stem, reason))
        else:
            active_entries.append(entry)

    # Build a lookup of composable content by file path
    composable_content_map: dict[Path, str] = {}
    if composable_changes:
        for change in composable_changes:
            if change.has_changes:
                composable_content_map[change.file_path] = change.new_content

    # Compute confidence for each active entry
    confidence_map: dict[str, ConfidenceLevel] = {}
    for entry in active_entries:
        comp_source = ""
        if entry.composable and entry.composable.file_path in composable_content_map:
            comp_source = composable_content_map[entry.composable.file_path]
        if comp_source:
            confidence_map[entry.mixin_stem] = compute_confidence(comp_source, entry.warnings)
        elif any(w.severity == "error" for w in entry.warnings):
            confidence_map[entry.mixin_stem] = ConfidenceLevel.LOW
        elif entry.warnings:
            confidence_map[entry.mixin_stem] = ConfidenceLevel.MEDIUM
        else:
            confidence_map[entry.mixin_stem] = ConfidenceLevel.HIGH

    # Sort: LOW first, then MEDIUM, then HIGH (most urgent at top)
    _CONF_ORDER = {ConfidenceLevel.LOW: 0, ConfidenceLevel.MEDIUM: 1, ConfidenceLevel.HIGH: 2}
    active_entries.sort(key=lambda e: _CONF_ORDER.get(confidence_map[e.mixin_stem], 2))

    if not active_entries and not skipped_rows:
        return ""

    # Count totals
    all_warnings = [w for e in active_entries for w in e.warnings]
    error_count = sum(1 for w in all_warnings if w.severity == "error")
    warning_count = sum(1 for w in all_warnings if w.severity == "warning")
    info_count = sum(1 for w in all_warnings if w.severity == "info")

    lines: list[str] = []
    a = lines.append

    a("## Migration Summary\n")

    # Overview line
    total_count = len(active_entries) + len(skipped_rows)
    parts = [f"**{total_count} composable{'s' if total_count != 1 else ''}**"]
    if error_count:
        parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
    if warning_count:
        parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
    if info_count:
        parts.append(f"{info_count} info")
    a(" | ".join(parts))
    a("")
    a("---\n")

    # Per-mixin sections
    _SEVERITY_ICON = {"error": "\u274c", "warning": "\u26a0\ufe0f", "info": "\u2139\ufe0f"}
    _CONF_ICON = {ConfidenceLevel.LOW: "\u274c", ConfidenceLevel.MEDIUM: "\u26a0\ufe0f", ConfidenceLevel.HIGH: "\u2705"}

    for entry in active_entries:
        conf = confidence_map[entry.mixin_stem]
        icon = _CONF_ICON.get(conf, "\u2753")

        a(f"### {icon} {entry.mixin_stem} \u2014 Transformation confidence: {conf.value}\n")

        if not entry.warnings:
            # Only say "No manual changes needed" if the composable is truly clean
            comp_source = ""
            if entry.composable and entry.composable.file_path in composable_content_map:
                comp_source = composable_content_map[entry.composable.file_path]
            has_migration_comments = (
                '// MIGRATION:' in comp_source
                or '// TODO:' in comp_source
                or '// ⚠ MIGRATION' in comp_source
            )
            if conf == ConfidenceLevel.HIGH and not has_migration_comments:
                a("No manual changes needed.\n")
            else:
                a("Review generated composable for any remaining migration markers.\n")
            continue

        item_count = len(entry.warnings)
        a(f"> {item_count} item{'s' if item_count != 1 else ''} need{'s' if item_count == 1 else ''} attention\n")

        for warning in entry.warnings:
            sev_icon = _SEVERITY_ICON.get(warning.severity, "\u2753")
            a(f"- {sev_icon} **{warning.category}** ({warning.severity}): {warning.message}")
            a(f"")
            a(f"    **\u2192 {warning.action_required}**\n")

    # Skipped mixins table
    if skipped_rows:
        a("\n## Skipped Mixins (not migrated)\n")
        a("| Component | Mixin | Reason |")
        a("|---|---|---|")
        for comp_name, mixin_stem, reason in skipped_rows:
            a(f"| {comp_name} | {mixin_stem} | {reason} |")
        a("")

    return "\n".join(lines)
