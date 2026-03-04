"""Project-wide auto-migrate workflow: scan, patch composables, inject setup().

No file I/O is performed here. All changes are represented as FileChange objects.
The CLI shows the diff and writes files only after user confirmation.
"""
import re
from pathlib import Path

from ..core.component_analyzer import (
    extract_own_members, find_used_members, parse_imports, parse_mixins_array,
)
from ..core.composable_analyzer import (
    extract_all_identifiers, extract_function_name, extract_return_keys,
)
from ..core.composable_search import find_composable_dirs, search_for_composable
from ..core.file_resolver import compute_import_path, resolve_import_path
from ..core.mixin_analyzer import extract_lifecycle_hooks, extract_mixin_members
from ..core.warning_collector import collect_mixin_warnings
from ..models import (
    ComposableCoverage, FileChange, MigrationConfig, MigrationPlan, MigrationStatus,
    MixinEntry, MixinMembers,
)
from ..transform.composable_generator import (
    generate_composable_from_mixin,
    mixin_stem_to_composable_name,
)
from ..transform.composable_patcher import patch_composable
from ..transform.injector import (
    add_composable_import, add_vue_import, inject_setup,
    remove_import_line, remove_mixin_from_array,
)
from ..transform.lifecycle_converter import (
    convert_lifecycle_hooks, find_lifecycle_referenced_members, get_required_imports,
)


def _analyze_mixin_silent(
    local_name: str,
    import_path_str: str,
    component_path: Path,
    component_source: str,
    composable_dirs: list[Path],
    project_root: Path,
    component_own_members: set[str],
) -> MixinEntry | None:
    """Analyze a mixin without any interactive prompts or print output."""
    mixin_file = resolve_import_path(import_path_str, component_path)
    if not mixin_file:
        return None
    # R-7: normalize CRLF
    mixin_source = mixin_file.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
    members_dict = extract_mixin_members(mixin_source)
    members = MixinMembers(**members_dict)
    hooks = extract_lifecycle_hooks(mixin_source)
    used = find_used_members(component_source, members.all_names)

    entry = MixinEntry(
        local_name=local_name,
        mixin_path=mixin_file,
        mixin_stem=mixin_file.stem,
        members=members,
        lifecycle_hooks=hooks,
        used_members=used,
    )

    if not used:
        entry.compute_status()
        return entry

    matches = search_for_composable(mixin_file.stem, composable_dirs, project_root=project_root)
    composable_file = matches[0] if matches else None

    if composable_file:
        if len(matches) > 1:
            print(
                f"  [auto-migrate] Multiple composable candidates for {mixin_file.stem}; "
                f"using first match: {composable_file.name}"
            )
        comp_source = composable_file.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
        fn_name = extract_function_name(comp_source)
        if fn_name:
            coverage = ComposableCoverage(
                file_path=composable_file,
                fn_name=fn_name,
                import_path=compute_import_path(composable_file, project_root),
                all_identifiers=extract_all_identifiers(comp_source),
                return_keys=extract_return_keys(comp_source),
            )
            entry.composable = coverage
            entry.classification = coverage.classify_members(used, component_own_members)

    # Collect migration warnings
    mixin_warnings = collect_mixin_warnings(mixin_source, members, hooks)
    for w in mixin_warnings:
        w.mixin_stem = entry.mixin_stem
    entry.warnings = mixin_warnings

    entry.compute_status()
    return entry


def collect_all_mixin_entries(
    project_root: Path,
    config: MigrationConfig,
) -> list[tuple[Path, list[MixinEntry]]]:
    """Scan every .vue file and silently analyze all mixins.

    Returns list of (component_path, [MixinEntry, ...]) for components
    that have at least one processable mixin.
    """
    composable_dirs = find_composable_dirs(project_root)
    result = []
    for vue_file in sorted(project_root.rglob("*.vue")):
        if any(skip in vue_file.parts for skip in config.skip_dirs):
            continue
        # R-7: normalize CRLF
        source = vue_file.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
        mixin_names = parse_mixins_array(source)
        if not mixin_names:
            continue
        all_imports = parse_imports(source)
        own_members = extract_own_members(source)
        entries = []
        for name in mixin_names:
            imp = all_imports.get(name)
            if not imp:
                continue
            entry = _analyze_mixin_silent(
                name, imp, vue_file, source,
                composable_dirs, project_root, own_members,
            )
            if entry:
                entries.append(entry)
        if entries:
            result.append((vue_file, entries))
    return result


def plan_composable_patches(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
) -> list[FileChange]:
    """Plan all composable patches needed across the project.

    De-duplicates: if two components share a composable, their required
    patches are merged by applying them sequentially to the same in-memory
    content.
    """
    patch_map: dict[Path, dict] = {}

    for _comp_path, entries in entries_by_component:
        for entry in entries:
            if entry.status not in (
                MigrationStatus.BLOCKED_NOT_RETURNED,
                MigrationStatus.BLOCKED_MISSING_MEMBERS,
            ):
                continue
            if not entry.composable or not entry.classification:
                continue
            comp_path = entry.composable.file_path
            if comp_path not in patch_map:
                patch_map[comp_path] = {
                    "content": comp_path.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n'),
                    "not_returned": set(),
                    "missing": set(),
                    "mixin_members": entry.members,
                    "mixin_content": entry.mixin_path.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n'),
                }
            rec = patch_map[comp_path]
            rec["not_returned"].update(entry.classification.truly_not_returned)
            rec["missing"].update(entry.classification.truly_missing)

    changes = []
    for comp_path, rec in patch_map.items():
        original = rec["content"]
        patched = patch_composable(
            composable_content=original,
            mixin_content=rec["mixin_content"],
            not_returned=list(rec["not_returned"]),
            missing=list(rec["missing"]),
            mixin_members=rec["mixin_members"],
        )
        change_descs = []
        if rec["not_returned"]:
            change_descs.append(f"Added to return: {', '.join(sorted(rec['not_returned']))}")
        if rec["missing"]:
            change_descs.append(f"Added declarations: {', '.join(sorted(rec['missing']))}")
        changes.append(FileChange(
            file_path=comp_path,
            original_content=original,
            new_content=patched,
            changes=change_descs,
        ))
    return changes


def plan_new_composables(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
    project_root: Path,
) -> list[FileChange]:
    """Generate new composable files for BLOCKED_NO_COMPOSABLE entries.

    For each unique mixin that has no composable at all, scaffolds a new
    composable file in the project's first composables directory.
    Returns FileChange objects with original_content="" (new files).
    """
    composable_dirs = find_composable_dirs(project_root)
    if composable_dirs:
        target_dir = composable_dirs[0]
    else:
        src_dir = project_root / "src"
        target_dir = (src_dir / "composables") if src_dir.is_dir() else (project_root / "composables")

    seen_stems: set[str] = set()
    changes = []

    for _comp_path, entries in entries_by_component:
        for entry in entries:
            if entry.status != MigrationStatus.BLOCKED_NO_COMPOSABLE:
                continue
            if entry.mixin_stem in seen_stems:
                continue
            seen_stems.add(entry.mixin_stem)

            mixin_source = entry.mixin_path.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
            fn_name = mixin_stem_to_composable_name(entry.mixin_stem)
            composable_path = target_dir / f"{fn_name}.js"

            content = generate_composable_from_mixin(
                mixin_source=mixin_source,
                mixin_stem=entry.mixin_stem,
                mixin_members=entry.members,
                lifecycle_hooks=entry.lifecycle_hooks,
            )
            changes.append(FileChange(
                file_path=composable_path,
                original_content="",
                new_content=content,
                changes=[f"Generated composable from {entry.mixin_stem}"],
            ))

    return changes


def plan_component_injections(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
    composable_patches: list[FileChange],
    config: MigrationConfig,
) -> list[FileChange]:
    """Plan all component setup() injections, including lifecycle hook conversion.

    Re-classifies entries whose composables were patched to account for
    the updated return_keys and identifiers.
    """
    patched_content: dict[Path, str] = {
        c.file_path: c.new_content for c in composable_patches if c.has_changes
    }

    # Build lookup of generated composables by fn_name (original_content == "" → new file)
    generated_by_fn_name: dict[str, FileChange] = {}
    for change in composable_patches:
        if change.original_content == "" and change.has_changes:
            fn_name = extract_function_name(change.new_content)
            if fn_name:
                generated_by_fn_name[fn_name] = change

    component_changes = []

    for comp_path, entries in entries_by_component:
        # R-7: normalize CRLF
        comp_source = comp_path.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
        own_members = extract_own_members(comp_source)
        ready_entries = []

        for entry in entries:
            # Re-classify patched existing composables
            if (
                entry.composable
                and entry.composable.file_path in patched_content
                and entry.status in (
                    MigrationStatus.BLOCKED_NOT_RETURNED,
                    MigrationStatus.BLOCKED_MISSING_MEMBERS,
                )
            ):
                new_content = patched_content[entry.composable.file_path]
                updated = ComposableCoverage(
                    file_path=entry.composable.file_path,
                    fn_name=entry.composable.fn_name,
                    import_path=entry.composable.import_path,
                    all_identifiers=extract_all_identifiers(new_content),
                    return_keys=extract_return_keys(new_content),
                )
                entry.composable = updated
                entry.classification = updated.classify_members(entry.used_members, own_members)
                entry.compute_status()

            # Re-classify BLOCKED_NO_COMPOSABLE entries that have a generated composable
            elif entry.status == MigrationStatus.BLOCKED_NO_COMPOSABLE and not entry.composable:
                expected_fn = mixin_stem_to_composable_name(entry.mixin_stem)
                if expected_fn in generated_by_fn_name:
                    change = generated_by_fn_name[expected_fn]
                    coverage = ComposableCoverage(
                        file_path=change.file_path,
                        fn_name=expected_fn,
                        import_path=compute_import_path(change.file_path, config.project_root),
                        all_identifiers=extract_all_identifiers(change.new_content),
                        return_keys=extract_return_keys(change.new_content),
                    )
                    entry.composable = coverage
                    entry.classification = coverage.classify_members(entry.used_members, own_members)
                    entry.compute_status()

            if entry.status == MigrationStatus.READY:
                ready_entries.append(entry)

        if not ready_entries:
            continue

        content = comp_source
        changes_desc = []

        for entry in ready_entries:
            new = remove_import_line(content, entry.mixin_stem)
            if new != content:
                changes_desc.append(f"Removed import {entry.mixin_stem}")
                content = new
            injectable = entry.classification.injectable if entry.classification else entry.used_members
            if injectable and entry.composable:
                new = add_composable_import(content, entry.composable.fn_name, entry.composable.import_path)
                if new != content:
                    changes_desc.append(f"Added import {{{entry.composable.fn_name}}}")
                    content = new

        for entry in ready_entries:
            new = remove_mixin_from_array(content, entry.local_name)
            if new != content:
                changes_desc.append(f"Removed {entry.local_name} from mixins")
                content = new

        composable_calls = []
        all_inline_lines: list[str] = []
        all_lifecycle_calls: list[str] = []

        for entry in ready_entries:
            injectable = list(entry.classification.injectable if entry.classification else entry.used_members)
            mixin_content = None

            # Augment injectable with members referenced in lifecycle hook bodies
            if entry.lifecycle_hooks and entry.composable:
                mixin_content = entry.mixin_path.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
                lifecycle_members = find_lifecycle_referenced_members(
                    mixin_content, entry.lifecycle_hooks, entry.members.all_names
                )
                for m in lifecycle_members:
                    if m not in injectable:
                        injectable.append(m)

            # Exclude members the component overrides — Options API takes
            # precedence over setup() returns, so injecting them is redundant.
            # Keep lifecycle-referenced members even if overridden, since the
            # composable's lifecycle wrapper closure may depend on them.
            if injectable and entry.composable:
                lifecycle_members_set = set(lifecycle_members) if entry.lifecycle_hooks else set()
                injectable = [
                    m for m in injectable
                    if m not in own_members or m in lifecycle_members_set
                ]

            if injectable and entry.composable:
                composable_calls.append((entry.composable.fn_name, injectable))

            if entry.lifecycle_hooks:
                if mixin_content is None:
                    mixin_content = entry.mixin_path.read_text(errors="ignore").replace('\r\n', '\n').replace('\r', '\n')
                ref_m = entry.members.data + entry.members.computed + entry.members.watch
                plain_m = entry.members.methods
                inline, wrapped = convert_lifecycle_hooks(
                    mixin_content, entry.lifecycle_hooks, ref_m, plain_m,
                    config.indent + config.indent,  # double indent to match setup() body level
                )
                all_inline_lines.extend(inline)
                all_lifecycle_calls.extend(wrapped)

                for hook_import in get_required_imports(entry.lifecycle_hooks):
                    content = add_vue_import(content, hook_import)

        if composable_calls or all_inline_lines or all_lifecycle_calls:
            new = inject_setup(
                content,
                composable_calls,
                config.indent,
                lifecycle_calls=all_lifecycle_calls or None,
                inline_setup_lines=all_inline_lines or None,
            )
            if new != content:
                fn_names = [c[0] for c in composable_calls]
                changes_desc.append(f"Injected setup() with {', '.join(fn_names)}")
                content = new

        if content != comp_source:
            content = re.sub(r"\n{3,}", "\n\n", content)

        component_changes.append(FileChange(
            file_path=comp_path,
            original_content=comp_source,
            new_content=content,
            changes=changes_desc,
        ))

    return component_changes


def _build_all_composable_changes(
    entries: list[tuple[Path, list[MixinEntry]]],
    project_root: Path,
) -> list[FileChange]:
    """Combine patched-existing + newly-generated composable changes."""
    patched = plan_composable_patches(entries)
    generated = plan_new_composables(entries, project_root)
    return patched + generated


def run(project_root: Path, config: MigrationConfig) -> MigrationPlan:
    """Main entry point: scan, plan composable patches, plan component injections.

    No file I/O. Returns a MigrationPlan the CLI can show as a diff and write.
    """
    entries = collect_all_mixin_entries(project_root, config)
    composable_changes = _build_all_composable_changes(entries, project_root)
    component_changes = plan_component_injections(entries, composable_changes, config)
    return MigrationPlan(
        component_changes=component_changes,
        composable_changes=composable_changes,
    )


def run_scoped(
    project_root: Path,
    config: MigrationConfig,
    component_path: "Path | None" = None,
    mixin_stem: "str | None" = None,
) -> MigrationPlan:
    """Run auto-migrate scoped to one component or one mixin stem.

    Exactly one of component_path or mixin_stem must be provided.
    No file I/O. Returns a MigrationPlan the CLI can show as a diff and write.
    """
    if component_path is None and mixin_stem is None:
        raise ValueError("Provide either component_path or mixin_stem")

    all_entries = collect_all_mixin_entries(project_root, config)

    if component_path is not None:
        entries = [(path, es) for path, es in all_entries if path == component_path]
    else:
        entries = [
            (path, [e for e in es if e.mixin_stem == mixin_stem])
            for path, es in all_entries
            if any(e.mixin_stem == mixin_stem for e in es)
        ]

    composable_changes = _build_all_composable_changes(entries, project_root)
    component_changes = plan_component_injections(entries, composable_changes, config)
    return MigrationPlan(
        component_changes=component_changes,
        composable_changes=composable_changes,
    )
