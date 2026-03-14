"""Project-wide auto-migrate workflow: scan, patch composables, inject setup().

No file I/O is performed here. All changes are represented as FileChange objects.
The CLI shows the diff and writes files only after user confirmation.
"""
import re
from pathlib import Path

from ..core.file_utils import read_source
from ..core.component_analyzer import (
    extract_data_property_names, extract_own_members, extract_setup_identifiers,
    find_used_members, parse_imports, parse_mixins_array,
)
from ..core.composable_analyzer import (
    classify_all_identifier_kinds,
    extract_all_identifiers, extract_declared_identifiers,
    extract_function_name, extract_return_keys,
)
from ..core.composable_search import find_composable_dirs, search_for_composable
from ..core.file_resolver import compute_import_path, resolve_import_path
from ..core.mixin_analyzer import (
    extract_lifecycle_hooks, extract_mixin_members,
    find_external_this_refs,
)
from ..core.warning_collector import collect_mixin_warnings, detect_name_collisions, suppress_resolved_warnings
from ..models import (
    ComposableCoverage, FileChange, MigrationConfig, MigrationPlan, MigrationStatus,
    MigrationWarning, MixinEntry, MixinMembers,
)
from ..transform.composable_generator import (
    generate_composable_from_mixin, mixin_stem_to_composable_name,
)
from ..transform.composable_patcher import patch_composable
from ..transform.injector import (
    add_composable_import, inject_setup,
    remove_import_line, remove_mixin_from_array,
)
from ..transform.lifecycle_converter import find_lifecycle_referenced_members


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
    mixin_source = read_source(mixin_file)
    members_dict = extract_mixin_members(mixin_source)
    members = MixinMembers(**members_dict)
    hooks = extract_lifecycle_hooks(mixin_source)
    used = find_used_members(component_source, members.all_names)

    ext_deps = find_external_this_refs(mixin_source, members.all_names)

    entry = MixinEntry(
        local_name=local_name,
        mixin_path=mixin_file,
        mixin_stem=mixin_file.stem,
        members=members,
        lifecycle_hooks=hooks,
        used_members=used,
        external_deps=ext_deps,
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
        comp_source = read_source(composable_file)
        fn_name = extract_function_name(comp_source)
        if fn_name:
            declared = extract_declared_identifiers(comp_source)
            coverage = ComposableCoverage(
                file_path=composable_file,
                fn_name=fn_name,
                import_path=compute_import_path(composable_file, project_root),
                all_identifiers=extract_all_identifiers(comp_source),
                declared_identifiers=declared,
                return_keys=extract_return_keys(comp_source),
                identifier_kinds=classify_all_identifier_kinds(comp_source, declared),
            )
            entry.composable = coverage
            entry.classification = coverage.classify_members(used, component_own_members, mixin_members=members)

            # Surface kind mismatches as warnings
            if entry.classification.kind_mismatched:
                for name, mixin_kind, comp_kind in entry.classification.kind_mismatched:
                    _kind_labels = {"data": "ref", "computed": "computed", "methods": "function"}
                    expected = _kind_labels.get(mixin_kind, mixin_kind)
                    entry.warnings.append(MigrationWarning(
                        mixin_stem=entry.mixin_stem,
                        category="kind-mismatch",
                        message=f"'{name}' is {mixin_kind} in mixin but {comp_kind} in composable — runtime type mismatch likely",
                        action_required=f"Change '{name}' in composable from {comp_kind} to {expected} to match mixin usage",
                        line_hint=None,
                        severity="warning",
                        source_context="composable",
                    ))

    # Collect migration warnings
    mixin_warnings = collect_mixin_warnings(
        mixin_source, members, hooks,
        mixin_path=mixin_file,
        project_root=project_root,
    )
    for w in mixin_warnings:
        w.mixin_stem = entry.mixin_stem
        w.source_context = "mixin"

    # Suppress warnings already resolved by the composable
    if entry.composable:
        comp_source = read_source(entry.composable.file_path)
        mixin_warnings = suppress_resolved_warnings(
            mixin_warnings,
            entry.composable.declared_identifiers,
            comp_source,
        )
        resolved_names = set(entry.composable.declared_identifiers)
        entry.external_deps = [d for d in entry.external_deps if d not in resolved_names]

    entry.warnings.extend(mixin_warnings)

    # Detect direct mixin object access in the component (e.g. searchMixin.methods.doX)
    from ..core.warning_collector import detect_direct_mixin_access
    direct_access_warnings = detect_direct_mixin_access(
        component_source, local_name, entry.mixin_stem,
        component_path=component_path,
    )
    entry.warnings.extend(direct_access_warnings)

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
        source = read_source(vue_file)
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
    project_root: "Path | None" = None,
) -> list[FileChange]:
    """Plan all composable patches needed across the project.

    De-duplicates: if two components share a composable, their required
    patches are merged by applying them sequentially to the same in-memory
    content.
    """
    patch_map: dict[Path, dict] = {}

    for _comp_path, entries in entries_by_component:
        for entry in entries:
            if not entry.composable:
                continue
            has_blocked = (
                entry.status in (
                    MigrationStatus.BLOCKED_NOT_RETURNED,
                    MigrationStatus.BLOCKED_MISSING_MEMBERS,
                )
                and entry.classification
            )
            has_hooks = bool(entry.lifecycle_hooks)
            if not has_blocked and not has_hooks:
                continue
            comp_path = entry.composable.file_path
            if comp_path not in patch_map:
                patch_map[comp_path] = {
                    "content": read_source(comp_path),
                    "not_returned": set(),
                    "missing": set(),
                    "lifecycle_hooks": [],
                    "mixin_members": entry.members,
                    "mixin_content": read_source(entry.mixin_path),
                    "mixin_path": entry.mixin_path,
                }
            rec = patch_map[comp_path]

            # Warn when the composable uses reactive() — the patcher will add
            # standalone ref()/computed() declarations alongside the existing
            # reactive() state, which creates two competing reactivity patterns
            # in the same file.
            if has_blocked and "reactive(" in rec["content"]:
                missing_names = sorted(
                    entry.classification.truly_missing
                    + entry.classification.truly_not_returned
                )
                if missing_names:
                    names_str = ", ".join(missing_names)
                    entry.warnings.append(MigrationWarning(
                        mixin_stem=entry.mixin_stem,
                        category="mixed-reactivity-pattern",
                        message=(
                            f"Composable '{entry.composable.fn_name}' uses reactive() but "
                            f"the patched members ({names_str}) were added as standalone "
                            "ref()/computed() declarations. This mixes two reactivity "
                            "patterns in the same file."
                        ),
                        action_required=(
                            f"Consolidate '{entry.composable.fn_name}' to use one pattern: "
                            f"either move {names_str} into the existing reactive() object, "
                            "or convert the reactive() state to individual ref() calls."
                        ),
                        line_hint=None,
                        severity="warning",
                        source_context="composable",
                    ))

            if has_blocked:
                rec["not_returned"].update(entry.classification.truly_not_returned)
                rec["missing"].update(entry.classification.truly_missing)
            if has_hooks:
                for h in entry.lifecycle_hooks:
                    if h not in rec["lifecycle_hooks"]:
                        rec["lifecycle_hooks"].append(h)

    changes = []
    for comp_path, rec in patch_map.items():
        original = rec["content"]
        patched = patch_composable(
            composable_content=original,
            mixin_content=rec["mixin_content"],
            not_returned=list(rec["not_returned"]),
            missing=list(rec["missing"]),
            mixin_members=rec["mixin_members"],
            lifecycle_hooks=rec["lifecycle_hooks"] or None,
            mixin_path=rec["mixin_path"],
            composable_path=comp_path,
            project_root=project_root,
        )
        change_descs = []
        if rec["not_returned"]:
            change_descs.append(f"Added to return: {', '.join(sorted(rec['not_returned']))}")
        if rec["missing"]:
            change_descs.append(f"Added declarations: {', '.join(sorted(rec['missing']))}")
        if rec["lifecycle_hooks"]:
            change_descs.append(f"Added lifecycle hooks: {', '.join(rec['lifecycle_hooks'])}")
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

            mixin_source = read_source(entry.mixin_path)
            fn_name = mixin_stem_to_composable_name(entry.mixin_stem)
            composable_path = target_dir / f"{fn_name}.js"

            content = generate_composable_from_mixin(
                mixin_source=mixin_source,
                mixin_stem=entry.mixin_stem,
                mixin_members=entry.members,
                lifecycle_hooks=entry.lifecycle_hooks,
                mixin_path=entry.mixin_path,
                composable_path=composable_path,
                project_root=project_root,
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
    """Plan all component setup() injections.

    Lifecycle hooks live in the composable (generated or patched), never in
    setup(). Members referenced in lifecycle hook bodies are included in the
    composable destructure so the hooks can access them.

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
        # Skip standalone entries (mixin-only, no component)
        if not comp_path.exists():
            continue
        # R-7: normalize CRLF
        comp_source = read_source(comp_path)
        own_members = extract_own_members(comp_source)
        setup_ids = extract_setup_identifiers(comp_source)
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
                declared = extract_declared_identifiers(new_content)
                updated = ComposableCoverage(
                    file_path=entry.composable.file_path,
                    fn_name=entry.composable.fn_name,
                    import_path=entry.composable.import_path,
                    all_identifiers=extract_all_identifiers(new_content),
                    declared_identifiers=declared,
                    return_keys=extract_return_keys(new_content),
                    identifier_kinds=classify_all_identifier_kinds(new_content, declared),
                )
                entry.composable = updated
                entry.classification = updated.classify_members(entry.used_members, own_members, mixin_members=entry.members)
                entry.compute_status()

            # Re-classify BLOCKED_NO_COMPOSABLE entries that have a generated composable
            elif entry.status == MigrationStatus.BLOCKED_NO_COMPOSABLE and not entry.composable:
                expected_fn = mixin_stem_to_composable_name(entry.mixin_stem)
                if expected_fn in generated_by_fn_name:
                    change = generated_by_fn_name[expected_fn]
                    declared = extract_declared_identifiers(change.new_content)
                    coverage = ComposableCoverage(
                        file_path=change.file_path,
                        fn_name=expected_fn,
                        import_path=compute_import_path(change.file_path, config.project_root),
                        all_identifiers=extract_all_identifiers(change.new_content),
                        declared_identifiers=declared,
                        return_keys=extract_return_keys(change.new_content),
                        identifier_kinds=classify_all_identifier_kinds(change.new_content, declared),
                    )
                    entry.composable = coverage
                    entry.classification = coverage.classify_members(entry.used_members, own_members, mixin_members=entry.members)
                    entry.compute_status()

            if entry.status == MigrationStatus.READY:
                ready_entries.append(entry)

        # Attach diagnostic warnings to blocked entries so the report
        # explains WHY each mixin was not migrated.
        blocked_entries = [e for e in entries if e.status not in (
            MigrationStatus.READY, MigrationStatus.FORCE_UNBLOCKED,
        )]
        for entry in blocked_entries:
            from ..models import MigrationWarning
            if entry.status == MigrationStatus.BLOCKED_NO_COMPOSABLE:
                if entry.composable:
                    detail = (
                        f"Composable '{entry.composable.fn_name}' was found "
                        "but could not be matched to this mixin's members."
                    )
                else:
                    detail = (
                        "No composable file was found for this mixin. "
                        "Generate one with the mixin command, or create it manually."
                    )
                entry.warnings.append(MigrationWarning(
                    mixin_stem=entry.mixin_stem,
                    category="blocked-no-composable",
                    message=(
                        f"Mixin '{entry.mixin_stem}' was NOT migrated: {detail}"
                    ),
                    action_required=(
                        "Create or generate a composable that covers this mixin's members, "
                        "then re-run the migration."
                    ),
                    line_hint=None,
                    severity="warning",
                    source_context="component",
                ))
            elif entry.status == MigrationStatus.BLOCKED_MISSING_MEMBERS:
                missing = (
                    ", ".join(entry.classification.truly_missing)
                    if entry.classification else "unknown"
                )
                fn_name = entry.composable.fn_name if entry.composable else "composable"
                entry.warnings.append(MigrationWarning(
                    mixin_stem=entry.mixin_stem,
                    category="blocked-missing-members",
                    message=(
                        f"Mixin '{entry.mixin_stem}' was NOT migrated: "
                        f"composable '{fn_name}' is missing members: {missing}."
                    ),
                    action_required=(
                        f"Add the missing members ({missing}) to '{fn_name}', "
                        "then re-run the migration."
                    ),
                    line_hint=None,
                    severity="warning",
                    source_context="component",
                ))
            elif entry.status == MigrationStatus.BLOCKED_NOT_RETURNED:
                not_returned = (
                    ", ".join(entry.classification.truly_not_returned)
                    if entry.classification else "unknown"
                )
                fn_name = entry.composable.fn_name if entry.composable else "composable"
                entry.warnings.append(MigrationWarning(
                    mixin_stem=entry.mixin_stem,
                    category="blocked-not-returned",
                    message=(
                        f"Mixin '{entry.mixin_stem}' was NOT migrated: "
                        f"composable '{fn_name}' declares but does not return: {not_returned}."
                    ),
                    action_required=(
                        f"Add {not_returned} to the return statement of '{fn_name}', "
                        "then re-run the migration."
                    ),
                    line_hint=None,
                    severity="warning",
                    source_context="component",
                ))

        if not ready_entries:
            continue

        # Detect member name collisions across composables for this component
        if len(ready_entries) > 1:
            composable_members_map = {}
            for entry in ready_entries:
                if entry.composable and entry.classification:
                    composable_members_map[entry.composable.fn_name] = list(
                        entry.classification.injectable
                    )
            collision_warnings = detect_name_collisions(composable_members_map)
            if collision_warnings:
                for w in collision_warnings:
                    w.mixin_stem = "cross-composable"
                    w.source_context = "component"
                ready_entries[0].warnings.extend(collision_warnings)

        # Detect data()/setup() name collisions (Issues #14, #20)
        data_props = extract_data_property_names(comp_source)
        if data_props:
            for entry in ready_entries:
                injectable = (
                    list(entry.classification.injectable)
                    if entry.classification
                    else list(entry.used_members)
                )
                collisions = set(injectable) & set(data_props)
                if collisions:
                    from ..models import MigrationWarning
                    for name in sorted(collisions):
                        entry.warnings.append(MigrationWarning(
                            mixin_stem=entry.mixin_stem,
                            category="data-setup-collision",
                            message=(
                                f"'{name}' is returned by both setup() and data(). "
                                "In Vue 3, data() properties take precedence over "
                                "setup() return values with the same name, so the "
                                "composable's value will be silently ignored."
                            ),
                            action_required=(
                                f"Remove '{name}' from data() to use the composable "
                                "value, or remove it from the composable return if the "
                                "component's data() version is intended."
                            ),
                            line_hint=None,
                            severity="warning",
                            source_context="component",
                        ))

        # Pre-compute which entries will produce a composable call.
        # Only migratable entries (those with injectable members) get their
        # mixin removed.  Entries that won't produce a composable call are
        # skipped and flagged for manual review.
        migratable_entries = []
        composable_calls = []
        seen_members: set[str] = set()

        for entry in ready_entries:
            injectable = list(entry.classification.injectable if entry.classification else entry.used_members)

            # Augment injectable with members referenced in lifecycle hook bodies —
            # the composable contains the hooks and needs these members destructured.
            lifecycle_members: list[str] = []
            if entry.lifecycle_hooks and entry.composable:
                mixin_content = read_source(entry.mixin_path)
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
            overridden_in_injectable: list[str] = []
            if injectable and entry.composable:
                lifecycle_members_set = set(lifecycle_members) if entry.lifecycle_hooks else set()
                overridden_in_injectable = [
                    m for m in injectable
                    if m in own_members and m not in lifecycle_members_set
                ]
                injectable = [
                    m for m in injectable
                    if m not in own_members or m in lifecycle_members_set
                ]

            # Also exclude members already declared in an existing setup()
            # to prevent "identifier already declared" errors during
            # incremental migration.
            setup_conflicts_in_injectable: list[str] = []
            if injectable and entry.composable and setup_ids:
                lifecycle_members_set = set(lifecycle_members) if entry.lifecycle_hooks else set()
                setup_conflicts_in_injectable = [
                    m for m in injectable
                    if m in setup_ids and m not in lifecycle_members_set
                ]
                injectable = [
                    m for m in injectable
                    if m not in setup_ids or m in lifecycle_members_set
                ]

            # Deduplicate cross-composable name collisions (first-wins)
            collision_skipped: list[str] = []
            if injectable and entry.composable:
                collision_skipped = [m for m in injectable if m in seen_members]
                injectable = [m for m in injectable if m not in seen_members]

            if injectable and entry.composable:
                migratable_entries.append(entry)
                composable_calls.append((entry.composable.fn_name, injectable))
                seen_members.update(injectable)
                # Warn about cross-composable collision dedup
                if collision_skipped:
                    from ..models import MigrationWarning
                    skipped_names = ", ".join(collision_skipped)
                    entry.warnings.append(MigrationWarning(
                        mixin_stem=entry.mixin_stem,
                        category="name-collision-skipped",
                        message=(
                            f"Skipped destructuring: {skipped_names} "
                            "(already provided by an earlier composable)."
                        ),
                        action_required=(
                            f"Verify the kept version of {skipped_names} is correct, "
                            "or rename in one composable."
                        ),
                        line_hint=None,
                        severity="warning",
                        source_context="component",
                    ))
                # Warn about setup() identifier conflicts
                if setup_conflicts_in_injectable:
                    from ..models import MigrationWarning
                    names = ", ".join(setup_conflicts_in_injectable)
                    entry.warnings.append(MigrationWarning(
                        mixin_stem=entry.mixin_stem,
                        category="setup-conflict",
                        message=(
                            f"Existing setup() already declares: {names}. "
                            "These are NOT destructured from the composable."
                        ),
                        action_required=(
                            f"Verify that the existing setup() declarations for "
                            f"{names} provide the same functionality as the composable."
                        ),
                        line_hint=None,
                        severity="info",
                        source_context="component",
                    ))
                # Warn about overridden members that won't be destructured
                if overridden_in_injectable:
                    from ..models import MigrationWarning
                    names = ", ".join(overridden_in_injectable)
                    entry.warnings.append(MigrationWarning(
                        mixin_stem=entry.mixin_stem,
                        category="overridden-member",
                        message=(
                            f"Component overrides mixin member(s): {names}. "
                            "These are NOT destructured from the composable."
                        ),
                        action_required=(
                            f"Verify that the component's own {names} "
                            "implementation does not depend on other mixin members."
                        ),
                        line_hint=None,
                        severity="info",
                        source_context="component",
                    ))
            else:
                # Entry won't produce a composable call — keep the mixin.
                from ..models import MigrationWarning
                if not entry.used_members:
                    if entry.lifecycle_hooks:
                        hooks_str = ", ".join(entry.lifecycle_hooks)
                        entry.warnings.append(MigrationWarning(
                            mixin_stem=entry.mixin_stem,
                            category="skipped-lifecycle-only",
                            message=(
                                f"Mixin '{entry.mixin_stem}' was NOT migrated: "
                                f"it provides lifecycle hooks ({hooks_str}) but "
                                "no members are directly referenced by the component."
                            ),
                            action_required=(
                                "Manually convert lifecycle hooks to the composable, "
                                "or remove the mixin if unused."
                            ),
                            line_hint=None,
                            severity="warning",
                            source_context="component",
                        ))
                    else:
                        entry.warnings.append(MigrationWarning(
                            mixin_stem=entry.mixin_stem,
                            category="skipped-no-usage",
                            message=(
                                f"Mixin '{entry.mixin_stem}' import and mixins "
                                "array entry removed: no members are referenced "
                                "by the component."
                            ),
                            action_required=(
                                "Verify the mixin was only used for members. "
                                "If it provides side-effect functionality "
                                "(e.g. event listeners, global state), "
                                "restore and manually convert."
                            ),
                            line_hint=None,
                            severity="info",
                            source_context="component",
                        ))
                else:
                    overridden_names = ", ".join(
                        entry.classification.overridden + entry.classification.overridden_not_returned
                    ) if entry.classification else ""
                    entry.warnings.append(MigrationWarning(
                        mixin_stem=entry.mixin_stem,
                        category="skipped-all-overridden",
                        message=(
                            f"Mixin '{entry.mixin_stem}' was NOT migrated: "
                            f"all used members ({overridden_names}) are overridden "
                            "by the component."
                        ),
                        action_required=(
                            "Remove the mixin if the component's overrides are "
                            "self-contained, or keep it if they depend on mixin internals."
                        ),
                        line_hint=None,
                        severity="info",
                        source_context="component",
                    ))

        # Collect entries whose mixin import/array entry should be removed
        # even though they won't get a composable call (no members used).
        removable_unused_entries = [
            e for e in ready_entries
            if e not in migratable_entries and not e.used_members
        ]

        content = comp_source
        changes_desc = []

        for entry in migratable_entries:
            new = remove_import_line(content, entry.mixin_stem)
            if new != content:
                changes_desc.append(f"Removed import {entry.mixin_stem}")
                content = new
            if entry.composable:
                new = add_composable_import(content, entry.composable.fn_name, entry.composable.import_path)
                if new != content:
                    changes_desc.append(f"Added import {{{entry.composable.fn_name}}}")
                    content = new

        # Remove imports for unused mixins (no members referenced by component)
        for entry in removable_unused_entries:
            new = remove_import_line(content, entry.mixin_stem)
            if new != content:
                changes_desc.append(f"Removed unused import {entry.mixin_stem}")
                content = new

        for entry in migratable_entries:
            new = remove_mixin_from_array(content, entry.local_name)
            if new != content:
                changes_desc.append(f"Removed {entry.local_name} from mixins")
                content = new

        # Remove unused mixins from the mixins array
        for entry in removable_unused_entries:
            new = remove_mixin_from_array(content, entry.local_name)
            if new != content:
                changes_desc.append(f"Removed unused {entry.local_name} from mixins")
                content = new

        if composable_calls:
            new = inject_setup(
                content,
                composable_calls,
                config.indent,
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


def plan_regenerated_composables(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
    project_root: Path,
) -> list[FileChange]:
    """Regenerate existing composables from their mixin source.

    For each mixin that HAS an existing composable on disk, generates
    fresh content using the generator instead of just patching.
    """
    seen_stems: set[str] = set()
    changes = []

    for _comp_path, entries in entries_by_component:
        for entry in entries:
            if entry.mixin_stem in seen_stems:
                continue
            # Only regenerate if composable already exists (not BLOCKED_NO_COMPOSABLE)
            if entry.status == MigrationStatus.BLOCKED_NO_COMPOSABLE:
                continue
            if not entry.composable:
                continue
            seen_stems.add(entry.mixin_stem)

            mixin_source = read_source(entry.mixin_path)
            content = generate_composable_from_mixin(
                mixin_source=mixin_source,
                mixin_stem=entry.mixin_stem,
                mixin_members=entry.members,
                lifecycle_hooks=entry.lifecycle_hooks,
                mixin_path=entry.mixin_path,
                composable_path=entry.composable.file_path,
                project_root=project_root,
            )
            original = read_source(entry.composable.file_path)
            if content != original:
                changes.append(FileChange(
                    file_path=entry.composable.file_path,
                    original_content=original,
                    new_content=content,
                    changes=[f"Regenerated composable from {entry.mixin_stem}"],
                ))
    return changes


def _inject_kind_mismatch_comments(
    source: str,
    warnings: list[MigrationWarning],
) -> str:
    """Add inline // ⚠️ comments to composable lines with kind mismatches."""
    import re
    _kind_labels = {"data": "ref", "computed": "computed", "methods": "function"}

    # Build member→hint map
    hints: dict[str, str] = {}
    for w in warnings:
        m = re.match(r"'(\w+)' is (\w+) in mixin but (\w+) in composable", w.message)
        if m:
            name, mixin_kind, comp_kind = m.group(1), m.group(2), m.group(3)
            expected = _kind_labels.get(mixin_kind, mixin_kind)
            hints[name] = f"\u26a0\ufe0f type mismatch \u2014 mixin expects {expected}, composable has {comp_kind}"

    if not hints:
        return source

    lines = source.splitlines(keepends=True)
    result = []
    for line in lines:
        stripped = line.rstrip("\n\r")
        # Skip comment-only lines
        if stripped.lstrip().startswith("//"):
            result.append(line)
            continue
        for name, hint in hints.items():
            # Match declaration of this identifier (const/let/var/function)
            if re.search(rf"\b(?:const|let|var)\s+{re.escape(name)}\b", stripped) or \
               re.search(rf"\bfunction\s+{re.escape(name)}\s*\(", stripped):
                # Don't double-annotate
                if hint not in stripped:
                    stripped = f"{stripped}  // {hint}"
                break
        result.append(stripped + line[len(line.rstrip("\n\r")):])
    return "".join(result)


def _build_all_composable_changes(
    entries: list[tuple[Path, list[MixinEntry]]],
    project_root: Path,
    config: MigrationConfig | None = None,
) -> list[FileChange]:
    """Combine patched-existing + newly-generated composable changes."""
    if config and config.regenerate:
        regenerated = plan_regenerated_composables(entries, project_root)
        generated = plan_new_composables(entries, project_root)
        return regenerated + generated
    patched = plan_composable_patches(entries, project_root=project_root)
    generated = plan_new_composables(entries, project_root)
    changes = patched + generated

    # Inject kind-mismatch inline comments into existing composables that
    # weren't patched or generated (i.e. READY composables with mismatches).
    changed_paths = {c.file_path for c in changes}
    kind_warnings = _collect_kind_mismatch_warnings(entries)
    for comp_path, warnings in kind_warnings.items():
        if comp_path in changed_paths:
            for change in changes:
                if change.file_path == comp_path:
                    change.new_content = _inject_kind_mismatch_comments(
                        change.new_content, warnings,
                    )
                    break
        else:
            original = read_source(comp_path)
            annotated = _inject_kind_mismatch_comments(original, warnings)
            if annotated != original:
                changes.append(FileChange(
                    file_path=comp_path,
                    original_content=original,
                    new_content=annotated,
                    changes=["Added kind-mismatch warning comments"],
                ))
    return changes


def _collect_kind_mismatch_warnings(
    entries: list[tuple[Path, list[MixinEntry]]],
) -> dict[Path, list[MigrationWarning]]:
    """Collect kind-mismatch warnings grouped by composable file path."""
    result: dict[Path, list[MigrationWarning]] = {}
    seen: set[tuple[Path, str]] = set()  # (comp_path, member_name) dedup
    for _comp_path, entry_list in entries:
        for entry in entry_list:
            if not entry.composable or not entry.classification:
                continue
            for w in entry.warnings:
                if w.category != "kind-mismatch":
                    continue
                key = (entry.composable.file_path, w.message)
                if key in seen:
                    continue
                seen.add(key)
                result.setdefault(entry.composable.file_path, []).append(w)
    return result


def _find_standalone_mixin_stems(
    project_root: Path, config: MigrationConfig,
    known_stems: set[str],
) -> list[str]:
    """Find mixin files on disk that aren't referenced by any component."""
    standalone: list[str] = []
    skip = config.skip_dirs
    for dirpath, dirnames, filenames in __import__("os").walk(project_root):
        rel = Path(dirpath).relative_to(project_root)
        if any(part in skip for part in rel.parts):
            dirnames.clear()
            continue
        is_mixin_dir = Path(dirpath).name.lower() == "mixins"
        for fn in filenames:
            fp = Path(fn)
            if fp.suffix not in (".js", ".ts"):
                continue
            if is_mixin_dir or "mixin" in fp.stem.lower():
                stem = fp.stem
                if stem not in known_stems:
                    standalone.append(stem)
                    known_stems.add(stem)
    return standalone


def _warn_unused_mixin_members(
    entries_by_component: list[tuple[Path, list[MixinEntry]]],
) -> None:
    """Attach warnings for mixin members not used by any component.

    Groups entries by mixin_stem, unions all used_members across components,
    and compares against members.all_names to find globally unused members.
    Standalone entries (Path("<standalone>")) are skipped.
    """
    # Group entries by mixin_stem, excluding standalone entries
    by_stem: dict[str, list[MixinEntry]] = {}
    for comp_path, entry_list in entries_by_component:
        if comp_path == Path("<standalone>"):
            continue
        for entry in entry_list:
            by_stem.setdefault(entry.mixin_stem, []).append(entry)

    for stem, stem_entries in by_stem.items():
        # Union of used_members across all components for this mixin
        all_used: set[str] = set()
        for entry in stem_entries:
            all_used.update(entry.used_members)

        # Use the first entry's members as the canonical definition
        members = stem_entries[0].members
        all_defined = members.all_names
        unused = [name for name in all_defined if name not in all_used]

        if not unused:
            continue

        # Build a section lookup for readable messages
        section_map: dict[str, str] = {}
        for name in members.data:
            section_map[name] = "data"
        for name in members.computed:
            section_map[name] = "computed"
        for name in members.methods:
            section_map[name] = "methods"
        for name in members.watch:
            section_map[name] = "watch"

        warnings = []
        for name in unused:
            section = section_map.get(name, "unknown")
            warnings.append(MigrationWarning(
                mixin_stem=stem,
                category="unused-mixin-member",
                message=f"'{name}' ({section}) defined in mixin but not used by any component",
                action_required=f"Review whether '{name}' is needed; remove from composable if unused",
                line_hint=None,
                severity="info",
            ))

        # Attach warnings to every entry for this mixin
        for entry in stem_entries:
            entry.warnings.extend(warnings)


def run(project_root: Path, config: MigrationConfig) -> MigrationPlan:
    """Main entry point: scan, plan composable patches, plan component injections.

    No file I/O. Returns a MigrationPlan the CLI can show as a diff and write.
    """
    entries = collect_all_mixin_entries(project_root, config)

    # Also include standalone mixins (not referenced by any component)
    known_stems = {e.mixin_stem for _, elist in entries for e in elist}
    for stem in _find_standalone_mixin_stems(project_root, config, known_stems):
        standalone = _build_standalone_mixin_entry(stem, project_root)
        entries.extend(standalone)

    _warn_unused_mixin_members(entries)

    composable_changes = _build_all_composable_changes(entries, project_root, config)
    component_changes = plan_component_injections(entries, composable_changes, config)
    return MigrationPlan(
        component_changes=component_changes,
        composable_changes=composable_changes,
        entries_by_component=entries,
    )


def _build_standalone_mixin_entry(
    mixin_stem: str, project_root: Path,
) -> list[tuple[Path, list[MixinEntry]]]:
    """Build a synthetic MixinEntry for a mixin not used by any component.

    This allows generating a composable from the mixin even when no
    component references it. Returns empty list if the mixin file is not
    found or a composable already exists.
    """
    mixin_file = None
    skip = {"node_modules", "dist", ".git", "__pycache__"}
    for path in sorted(project_root.rglob(f"{mixin_stem}.js")):
        if not any(p in skip for p in path.parts):
            mixin_file = path
            break
    if not mixin_file:
        for path in sorted(project_root.rglob(f"{mixin_stem}.ts")):
            if not any(p in skip for p in path.parts):
                mixin_file = path
                break
    if not mixin_file:
        return []

    composable_dirs = find_composable_dirs(project_root)
    matches = search_for_composable(mixin_stem, composable_dirs, project_root=project_root)

    mixin_source = read_source(mixin_file)
    members_dict = extract_mixin_members(mixin_source)
    members = MixinMembers(**members_dict)
    hooks = extract_lifecycle_hooks(mixin_source)
    ext_deps = find_external_this_refs(mixin_source, members.all_names)

    entry = MixinEntry(
        local_name=mixin_stem,
        mixin_path=mixin_file,
        mixin_stem=mixin_stem,
        members=members,
        lifecycle_hooks=hooks,
        used_members=members.all_names,
        external_deps=ext_deps,
        status=MigrationStatus.BLOCKED_NO_COMPOSABLE,
    )

    # If a composable already exists, attach it so it can be re-patched
    if matches:
        composable_file = matches[0]
        comp_source = read_source(composable_file)
        fn_name = extract_function_name(comp_source)
        if fn_name:
            declared = extract_declared_identifiers(comp_source)
            entry.composable = ComposableCoverage(
                file_path=composable_file,
                fn_name=fn_name,
                import_path=compute_import_path(composable_file, project_root),
                all_identifiers=extract_all_identifiers(comp_source),
                declared_identifiers=declared,
                return_keys=extract_return_keys(comp_source),
                identifier_kinds=classify_all_identifier_kinds(comp_source, declared),
            )
            entry.classification = entry.composable.classify_members(
                members.all_names, set(), mixin_members=members,
            )

    mixin_warnings = collect_mixin_warnings(
        mixin_source, members, hooks,
        mixin_path=mixin_file,
        project_root=project_root,
    )
    for w in mixin_warnings:
        w.mixin_stem = entry.mixin_stem
        w.source_context = "mixin"

    # Suppress warnings already resolved by the composable
    if entry.composable:
        comp_source = read_source(entry.composable.file_path)
        mixin_warnings = suppress_resolved_warnings(
            mixin_warnings,
            entry.composable.declared_identifiers,
            comp_source,
        )
        resolved_names = set(entry.composable.declared_identifiers)
        entry.external_deps = [d for d in entry.external_deps if d not in resolved_names]

    entry.warnings.extend(mixin_warnings)

    # Flag this mixin as unused by any component — safe to delete
    entry.warnings.insert(0, MigrationWarning(
        mixin_stem=entry.mixin_stem,
        category="unused-mixin",
        message=(
            f"No component imports '{mixin_stem}'. "
            "This mixin file can be safely deleted."
        ),
        action_required=(
            f"Delete the mixin file or keep it if used outside "
            "this project (shared library, dynamic import, etc.)"
        ),
        line_hint=None,
        severity="info",
        source_context="mixin",
    ))

    entry.compute_status()

    # Use a sentinel path to indicate no real component
    return [(Path("<standalone>"), [entry])]


def run_scoped(
    project_root: Path,
    config: MigrationConfig,
    component_path: "Path | None" = None,
    mixin_stem: "str | None" = None,
) -> MigrationPlan:
    """Run auto-migrate scoped to one component or one mixin stem.

    Exactly one of component_path or mixin_stem must be provided.
    No file I/O. Returns a MigrationPlan the CLI can show as a diff and write.

    Note: When component_path is provided, composable patches only aggregate
    requirements from that component's entries. Shared composables may receive
    incomplete patches. Use mixin_stem scope or full-project run for complete
    composable coverage.
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

    # If no components use this mixin, try to generate the composable standalone
    if not entries and mixin_stem is not None:
        entries = _build_standalone_mixin_entry(mixin_stem, project_root)

    # If components include the mixin but none trigger composable work
    # (e.g. no members are referenced → READY with composable=None),
    # add a standalone entry so the composable is still generated/patched.
    if entries and mixin_stem is not None:
        any_composable_work = any(
            e.composable is not None
            or e.status == MigrationStatus.BLOCKED_NO_COMPOSABLE
            for _, es in entries for e in es
        )
        if not any_composable_work:
            standalone = _build_standalone_mixin_entry(mixin_stem, project_root)
            entries.extend(standalone)

    # Use all_entries for unused-member analysis so the union of used_members
    # spans every component in the project, not just the scoped subset.
    _warn_unused_mixin_members(all_entries)

    composable_changes = _build_all_composable_changes(entries, project_root, config)
    component_changes = plan_component_injections(entries, composable_changes, config)
    return MigrationPlan(
        component_changes=component_changes,
        composable_changes=composable_changes,
        entries_by_component=entries,
    )
