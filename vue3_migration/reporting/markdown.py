"""
Markdown report generation for migration analysis results.
"""

from pathlib import Path

from ..models import MixinEntry
from .terminal import md_green, md_yellow


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
