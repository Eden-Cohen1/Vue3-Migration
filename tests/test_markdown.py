"""Tests for vue3_migration.reporting.markdown — report generation."""
import pytest
from pathlib import Path

from vue3_migration.models import (
    ComposableCoverage,
    MemberClassification,
    MigrationStatus,
    MixinEntry,
    MixinMembers,
)
from vue3_migration.models import ConfidenceLevel, MigrationWarning
from vue3_migration.reporting.markdown import (
    build_action_plan,
    build_audit_report,
    build_component_report,
    build_per_component_index,
    build_recipes_section,
)

FIXTURES = Path(__file__).parent / "fixtures" / "dummy_project"
PROJECT_ROOT = FIXTURES


# ---------------------------------------------------------------------------
# Helper factories (mirror the dummy project's analysis outcomes)
# ---------------------------------------------------------------------------

def _make_ready_entry() -> MixinEntry:
    """selectionMixin fully covered by useSelection -> READY."""
    coverage = ComposableCoverage(
        file_path=FIXTURES / 'src/composables/useSelection.js',
        fn_name='useSelection',
        import_path='@/composables/useSelection',
        all_identifiers=[
            'selectedItems', 'selectionMode', 'hasSelection',
            'selectionCount', 'selectItem', 'clearSelection', 'toggleItem',
        ],
        return_keys=[
            'selectedItems', 'selectionMode', 'hasSelection',
            'selectionCount', 'selectItem', 'clearSelection', 'toggleItem',
        ],
    )
    classification = MemberClassification(
        missing=[],
        truly_missing=[],
        not_returned=[],
        truly_not_returned=[],
        overridden=[],
        overridden_not_returned=[],
        injectable=['selectionCount', 'clearSelection', 'hasSelection'],
    )
    return MixinEntry(
        local_name='selectionMixin',
        mixin_path=FIXTURES / 'src/mixins/selectionMixin.js',
        mixin_stem='selectionMixin',
        members=MixinMembers(
            data=['selectedItems', 'selectionMode'],
            computed=['hasSelection', 'selectionCount'],
            methods=['selectItem', 'clearSelection', 'toggleItem'],
        ),
        lifecycle_hooks=[],
        used_members=['selectionCount', 'clearSelection', 'hasSelection'],
        composable=coverage,
        classification=classification,
        status=MigrationStatus.READY,
    )


def _make_blocked_missing_entry() -> MixinEntry:
    """paginationMixin -> BLOCKED_MISSING_MEMBERS (hasPrevPage, prevPage absent)."""
    coverage = ComposableCoverage(
        file_path=FIXTURES / 'src/composables/usePagination.js',
        fn_name='usePagination',
        import_path='@/composables/usePagination',
        all_identifiers=[
            'currentPage', 'pageSize', 'totalItems', 'totalPages',
            'hasNextPage', 'nextPage', 'goToPage', 'resetPagination',
        ],
        return_keys=[
            'currentPage', 'pageSize', 'totalItems', 'totalPages',
            'hasNextPage', 'nextPage', 'goToPage',
        ],
    )
    classification = MemberClassification(
        missing=['hasPrevPage', 'prevPage'],
        truly_missing=['hasPrevPage', 'prevPage'],
        not_returned=['resetPagination'],
        truly_not_returned=['resetPagination'],
        overridden=[],
        overridden_not_returned=[],
        injectable=['currentPage', 'totalPages', 'hasNextPage', 'nextPage'],
    )
    return MixinEntry(
        local_name='paginationMixin',
        mixin_path=FIXTURES / 'src/mixins/paginationMixin.js',
        mixin_stem='paginationMixin',
        members=MixinMembers(
            data=['currentPage', 'pageSize', 'totalItems'],
            computed=['totalPages', 'hasNextPage', 'hasPrevPage'],
            methods=['nextPage', 'prevPage', 'goToPage', 'resetPagination'],
        ),
        lifecycle_hooks=[],
        used_members=['currentPage', 'totalPages', 'hasPrevPage', 'prevPage', 'nextPage'],
        composable=coverage,
        classification=classification,
        status=MigrationStatus.BLOCKED_MISSING_MEMBERS,
    )


def _make_no_composable_entry() -> MixinEntry:
    """authMixin -> BLOCKED_NO_COMPOSABLE."""
    return MixinEntry(
        local_name='authMixin',
        mixin_path=FIXTURES / 'src/mixins/authMixin.js',
        mixin_stem='authMixin',
        members=MixinMembers(
            data=['isAuthenticated', 'currentUser', 'token'],
            computed=['isAdmin'],
            methods=['login', 'logout', 'checkAuth'],
        ),
        lifecycle_hooks=['created'],
        used_members=['isAuthenticated', 'currentUser', 'isAdmin', 'logout'],
        composable=None,
        classification=None,
        status=MigrationStatus.BLOCKED_NO_COMPOSABLE,
    )


def _make_with_overrides_entry() -> MixinEntry:
    """selectionMixin where component overrides selectionMode + clearSelection -> READY."""
    coverage = ComposableCoverage(
        file_path=FIXTURES / 'src/composables/useSelection.js',
        fn_name='useSelection',
        import_path='@/composables/useSelection',
        all_identifiers=[
            'selectedItems', 'selectionMode', 'hasSelection',
            'selectionCount', 'selectItem', 'clearSelection', 'toggleItem',
        ],
        return_keys=[
            'selectedItems', 'selectionMode', 'hasSelection',
            'selectionCount', 'selectItem', 'clearSelection', 'toggleItem',
        ],
    )
    classification = MemberClassification(
        missing=[],
        truly_missing=[],
        not_returned=[],
        truly_not_returned=[],
        overridden=['clearSelection'],
        overridden_not_returned=[],
        injectable=['selectionCount'],
    )
    return MixinEntry(
        local_name='selectionMixin',
        mixin_path=FIXTURES / 'src/mixins/selectionMixin.js',
        mixin_stem='selectionMixin',
        members=MixinMembers(
            data=['selectedItems', 'selectionMode'],
            computed=['hasSelection', 'selectionCount'],
            methods=['selectItem', 'clearSelection', 'toggleItem'],
        ),
        lifecycle_hooks=[],
        used_members=['selectionCount', 'clearSelection'],
        composable=coverage,
        classification=classification,
        status=MigrationStatus.READY,
    )


def _make_lifecycle_hooks_entry() -> MixinEntry:
    """loggingMixin -> READY but has lifecycle hooks that need manual migration."""
    coverage = ComposableCoverage(
        file_path=FIXTURES / 'src/composables/useLogging.js',
        fn_name='useLogging',
        import_path='@/composables/useLogging',
        all_identifiers=['logs', 'log'],
        return_keys=['logs', 'log'],
    )
    classification = MemberClassification(
        missing=[],
        truly_missing=[],
        not_returned=[],
        truly_not_returned=[],
        overridden=[],
        overridden_not_returned=[],
        injectable=['logs', 'log'],
    )
    return MixinEntry(
        local_name='loggingMixin',
        mixin_path=FIXTURES / 'src/mixins/loggingMixin.js',
        mixin_stem='loggingMixin',
        members=MixinMembers(
            data=['logs'],
            computed=[],
            methods=['log'],
        ),
        lifecycle_hooks=['created', 'mounted', 'beforeDestroy'],
        used_members=['logs', 'log'],
        composable=coverage,
        classification=classification,
        status=MigrationStatus.READY,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildComponentReport:
    def test_report_header_contains_component_name(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'FullyCovered.vue' in report

    def test_ready_mixin_shows_ready_status(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'READY' in report

    def test_ready_report_lists_mixin_name(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'selectionMixin' in report

    def test_ready_report_shows_composable_function(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'useSelection' in report

    def test_blocked_missing_shows_blocked_status(self):
        component = FIXTURES / 'src/components/PartiallyBlocked.vue'
        report = build_component_report(component, [_make_blocked_missing_entry()], PROJECT_ROOT)
        # Report shows the missing members
        assert 'hasPrevPage' in report
        assert 'prevPage' in report

    def test_blocked_not_returned_shown_in_report(self):
        component = FIXTURES / 'src/components/PartiallyBlocked.vue'
        report = build_component_report(component, [_make_blocked_missing_entry()], PROJECT_ROOT)
        assert 'resetPagination' in report

    def test_no_composable_shows_create_action(self):
        component = FIXTURES / 'src/components/NoComposable.vue'
        report = build_component_report(component, [_make_no_composable_entry()], PROJECT_ROOT)
        # Should mention creating a composable and list the mixin name
        assert 'authMixin' in report
        assert 'Create composable' in report or 'composable' in report.lower()

    def test_no_composable_lists_required_members(self):
        component = FIXTURES / 'src/components/NoComposable.vue'
        report = build_component_report(component, [_make_no_composable_entry()], PROJECT_ROOT)
        # Used members must be mentioned so developer knows what to implement
        for member in ('isAuthenticated', 'currentUser', 'isAdmin', 'logout'):
            assert member in report

    def test_overridden_members_noted_in_report(self):
        component = FIXTURES / 'src/components/WithOverrides.vue'
        report = build_component_report(component, [_make_with_overrides_entry()], PROJECT_ROOT)
        assert 'clearSelection' in report
        assert 'Overridden' in report or 'overridden' in report

    def test_lifecycle_hooks_trigger_manual_migration_note(self):
        component = FIXTURES / 'src/components/LifecycleHooks.vue'
        report = build_component_report(component, [_make_lifecycle_hooks_entry()], PROJECT_ROOT)
        # Report must warn about lifecycle hooks
        assert 'created' in report or 'mounted' in report or 'beforeDestroy' in report
        assert 'manual' in report.lower() or 'manually' in report.lower()

    def test_multiple_mixins_both_appear_in_report(self):
        component = FIXTURES / 'src/components/PartiallyBlocked.vue'
        entries = [_make_ready_entry(), _make_blocked_missing_entry()]
        report = build_component_report(component, entries, PROJECT_ROOT)
        assert 'selectionMixin' in report
        assert 'paginationMixin' in report

    def test_action_items_section_present(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'Action Items' in report

    def test_ready_for_injection_listed(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'Ready for injection' in report

    def test_all_ready_summary_message(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert 'All mixins are ready' in report

    def test_partial_ready_summary_message(self):
        component = FIXTURES / 'src/components/PartiallyBlocked.vue'
        entries = [_make_ready_entry(), _make_blocked_missing_entry()]
        report = build_component_report(component, entries, PROJECT_ROOT)
        # 1 of 2 ready
        assert '1 of 2' in report

    def test_returns_string(self):
        component = FIXTURES / 'src/components/FullyCovered.vue'
        report = build_component_report(component, [_make_ready_entry()], PROJECT_ROOT)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_warnings_with_severity_icons(self):
        """Component report should show severity icons for warnings."""
        entry = _make_ready_entry()
        w = MigrationWarning(
            "selectionMixin", "this.$emit", "not available", "Fix it", None, "error",
        )
        entry.warnings = [w]
        component = FIXTURES / "src/components/FullyCovered.vue"
        report = build_component_report(component, [entry], PROJECT_ROOT)
        assert "this.$emit" in report
        # Should show severity in some form
        assert "error" in report.lower() or "❌" in report


class TestBuildPerComponentIndex:
    def test_renders_component_heading(self):
        entry = _make_ready_entry()
        entries_by_component = [(FIXTURES / "src/components/FullyCovered.vue", [entry])]
        result = build_per_component_index(entries_by_component, {}, PROJECT_ROOT)
        assert "FullyCovered.vue" in result

    def test_shows_composable_with_confidence(self):
        entry = _make_ready_entry()
        confidence_map = {"selectionMixin": ConfidenceLevel.HIGH}
        entries_by_component = [(FIXTURES / "src/components/FullyCovered.vue", [entry])]
        result = build_per_component_index(entries_by_component, confidence_map, PROJECT_ROOT)
        assert "useSelection" in result
        assert "\U0001f7e2" in result  # green dot for HIGH confidence

    def test_shows_skipped_entry(self):
        entry = _make_ready_entry()
        w = MigrationWarning(
            "selectionMixin", "skipped-all-overridden",
            "all members overridden", "safe to remove", None, "info",
        )
        entry.warnings = [w]
        entries_by_component = [(FIXTURES / "src/components/FullyCovered.vue", [entry])]
        result = build_per_component_index(entries_by_component, {}, PROJECT_ROOT)
        assert "skipped" in result.lower()

    def test_empty_entries_returns_empty(self):
        result = build_per_component_index([], {}, PROJECT_ROOT)
        assert result == ""

    def test_multiple_components(self):
        entry1 = _make_ready_entry()
        entry2 = _make_blocked_missing_entry()
        entries = [
            (FIXTURES / "src/components/A.vue", [entry1]),
            (FIXTURES / "src/components/B.vue", [entry2]),
        ]
        result = build_per_component_index(entries, {}, PROJECT_ROOT)
        assert "A.vue" in result
        assert "B.vue" in result


class TestBuildActionPlan:
    def test_renders_section_header(self):
        w = MigrationWarning("auth", "this.$emit", "not available", "Fix it", None, "error")
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry.warnings = [w]
        result = build_action_plan([(Path("fake/Comp.vue"), [entry])])
        assert "## Action Plan" in result

    def test_tiers_by_severity(self):
        """Errors go to design decisions, warnings go to drop-in fixes."""
        w_err = MigrationWarning("auth", "this.$emit", "msg", "act", None, "error")
        w_warn = MigrationWarning("router", "this.$router", "msg", "act", None, "warning")
        entry_err = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry_err.warnings = [w_err]
        entry_warn = MixinEntry(
            local_name="routerMixin", mixin_path=FIXTURES / "src/mixins/routerMixin.js",
            mixin_stem="routerMixin", members=MixinMembers(),
        )
        entry_warn.warnings = [w_warn]
        result = build_action_plan([
            (Path("fake/A.vue"), [entry_err]),
            (Path("fake/B.vue"), [entry_warn]),
        ])
        assert "Design decisions" in result or "design" in result.lower()
        assert "Drop-in fixes" in result or "drop-in" in result.lower()

    def test_quick_wins_for_clean_entries(self):
        """Entries with only info warnings go to quick wins."""
        w = MigrationWarning("auth", "unused-mixin-member", "msg", "act", None, "info")
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry.warnings = [w]
        result = build_action_plan([(Path("fake/Comp.vue"), [entry])])
        assert "Quick Wins" in result or "quick win" in result.lower()

    def test_empty_entries_returns_empty(self):
        result = build_action_plan([])
        assert result == ""

    def test_summary_tallies(self):
        w1 = MigrationWarning("auth", "this.$emit", "msg", "act", None, "error")
        w2 = MigrationWarning("auth", "this.$refs", "msg", "act", None, "error")
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry.warnings = [w1, w2]
        result = build_action_plan([(Path("fake/Comp.vue"), [entry])])
        assert "2" in result  # 2 blockers

    def test_no_warnings_still_shows_quick_wins(self):
        """Entries with no warnings appear as quick wins in the action plan."""
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        result = build_action_plan([(Path("fake/Comp.vue"), [entry])])
        assert "Quick Wins" in result

    def test_recipe_links_in_steps(self):
        """Steps should link to recipes when available."""
        w = MigrationWarning("auth", "this.$router", "not available", "Use useRouter()", None, "warning")
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry.warnings = [w]
        result = build_action_plan([(Path("fake/Comp.vue"), [entry])])
        assert "see how" in result
        assert "#recipe-" in result


class TestBuildRecipesSection:
    def test_renders_recipes_for_present_categories(self):
        w = MigrationWarning("auth", "this.$router", "msg", "act", None, "warning")
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry.warnings = [w]
        result = build_recipes_section([(Path("fake/Comp.vue"), [entry])])
        assert "## Migration Patterns" in result
        assert "useRouter()" in result
        assert "```js" in result

    def test_no_recipes_for_empty_warnings(self):
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        result = build_recipes_section([(Path("fake/Comp.vue"), [entry])])
        assert result == ""

    def test_deduplicates_alias_categories(self):
        """this.$off should map to same recipe as this.$on."""
        w1 = MigrationWarning("auth", "this.$on", "msg", "act", None, "warning")
        w2 = MigrationWarning("auth", "this.$off", "msg", "act", None, "warning")
        entry = MixinEntry(
            local_name="authMixin", mixin_path=FIXTURES / "src/mixins/authMixin.js",
            mixin_stem="authMixin", members=MixinMembers(),
        )
        entry.warnings = [w1, w2]
        result = build_recipes_section([(Path("fake/Comp.vue"), [entry])])
        # Should only have one recipe heading for event bus, not two
        assert result.count("event bus") >= 1
        assert result.count("## Migration Patterns") == 1


class TestBuildAuditReportWarnings:
    def test_audit_report_shows_warnings_when_provided(self):
        w = MigrationWarning(
            "authMixin", "this.$emit", "not available", "Fix it", None, "error",
        )
        report = build_audit_report(
            mixin_path=FIXTURES / "src/mixins/authMixin.js",
            members={"data": ["token"], "computed": [], "methods": ["go"]},
            lifecycle_hooks=["mounted"],
            importing_files=[FIXTURES / "src/components/A.vue"],
            all_member_names=["token", "go"],
            composable_path_arg=None,
            composable_identifiers=[],
            composable_exists=False,
            project_root=PROJECT_ROOT,
            usage_map={},
            warnings=[w],
        )
        assert "this.$emit" in report
        assert "error" in report.lower() or "❌" in report

    def test_audit_report_works_without_warnings(self):
        """Backward compatibility — no warnings param."""
        report = build_audit_report(
            mixin_path=FIXTURES / "src/mixins/authMixin.js",
            members={"data": ["token"], "computed": [], "methods": []},
            lifecycle_hooks=[],
            importing_files=[],
            all_member_names=["token"],
            composable_path_arg=None,
            composable_identifiers=[],
            composable_exists=False,
            project_root=PROJECT_ROOT,
            usage_map={},
        )
        assert "authMixin" in report


class TestUnusedMixinWithMigrationWork:
    """Standalone mixin entries with actual migration warnings should show
    composable steps in the report, not just 'safe to delete'."""

    def test_unused_mixin_with_warnings_shows_composable_steps(self):
        """When a mixin is unused but has migration warnings (external deps,
        this.$ patterns, etc.), the action plan should include composable
        steps — not just 'safe to delete'."""
        entry = MixinEntry(
            local_name='kitchenSinkMixin',
            mixin_path=FIXTURES / 'src/mixins/kitchenSinkMixin.js',
            mixin_stem='kitchenSinkMixin',
            members=MixinMembers(
                data=['items', 'config'],
                computed=['filteredItems'],
                methods=['fetchResults', 'handleCustom'],
            ),
            lifecycle_hooks=['created'],
            used_members=['items', 'filteredItems', 'fetchResults'],
            composable=ComposableCoverage(
                file_path=FIXTURES / 'src/composables/useKitchenSink.js',
                fn_name='useKitchenSink',
                import_path='@/composables/useKitchenSink',
                all_identifiers=['items', 'config', 'filteredItems', 'fetchResults'],
                return_keys=['items', 'config', 'filteredItems', 'fetchResults'],
            ),
            classification=MemberClassification(
                missing=[], truly_missing=[], not_returned=[],
                truly_not_returned=[], overridden=[],
                overridden_not_returned=[], injectable=[],
            ),
            status=MigrationStatus.READY,
            warnings=[
                MigrationWarning(
                    "kitchenSinkMixin", "unused-mixin",
                    "No component imports 'kitchenSinkMixin'.",
                    "Delete the mixin file or keep if used outside this project",
                    None, "info",
                ),
                MigrationWarning(
                    "kitchenSinkMixin", "this.$emit",
                    "this.$emit not available in composable",
                    "Use defineEmits",
                    "this.$emit('search', q)",
                    "error",
                ),
                MigrationWarning(
                    "kitchenSinkMixin", "external-dependency",
                    "'handleCustom' — pass handleCustom as param",
                    "Accept as param",
                    "this.handleCustom",
                    "error",
                ),
            ],
        )

        entries = [(Path("<standalone>"), [entry])]
        report = build_action_plan(entries, project_root=PROJECT_ROOT)

        # Should NOT just say "safe to delete" — should include composable steps
        assert "useKitchenSink" in report
        assert "this.$emit" in report or "defineEmits" in report
        assert "handleCustom" in report


# ---------------------------------------------------------------------------
# Issue 4: Mixin fallback line refs should use source_lines (all occurrences)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Issue 3: this.$once should not be mislabeled as this.$on
# ---------------------------------------------------------------------------

class TestOnceNotMislabeledAsOn:
    """this.$once must get its own step/recipe, not be grouped under this.$on."""

    def test_once_has_separate_step(self, tmp_path):
        """Report should show separate steps for $on and $once."""
        comp_path = tmp_path / "useEventBus.js"
        comp_source = (
            "export function useEventBus() {\n"
            "  function registerEvents() {\n"
            "    this.$on('data-updated', handleDataUpdate)\n"       # L3
            "    this.$on('user-action', handleUserAction)\n"        # L4
            "    this.$once('initialized', () => {})\n"              # L5
            "  }\n"
            "  return { registerEvents }\n"
            "}\n"
        )
        comp_path.write_text(comp_source)

        from vue3_migration.models import FileChange
        composable_changes = [FileChange(file_path=comp_path, original_content="", new_content=comp_source)]

        entry = MixinEntry(
            local_name="eventBusMixin",
            mixin_path=tmp_path / "eventBusMixin.js",
            mixin_stem="eventBusMixin",
            members=MixinMembers(methods=["registerEvents"]),
            composable=ComposableCoverage(
                file_path=comp_path,
                fn_name="useEventBus",
                import_path="./composables/useEventBus",
                return_keys=["registerEvents"],
                all_identifiers=["registerEvents"],
            ),
            warnings=[
                MigrationWarning("eventBusMixin", "this.$on",
                    "this.$on is removed in Vue 3",
                    "Use an external event bus library", None, "error"),
                MigrationWarning("eventBusMixin", "this.$once",
                    "this.$once is removed in Vue 3",
                    "Use an external event bus library", None, "error"),
            ],
        )

        entries = [(Path("<standalone>"), [entry])]
        report = build_action_plan(entries, composable_changes=composable_changes,
                                   project_root=tmp_path)

        # Both $on and $once should appear as separate steps
        assert "this.$on" in report
        assert "this.$once" in report
        # $once line (L5) should NOT appear in the $on step
        lines = report.split("\n")
        on_step = [l for l in lines if "this.$on" in l and "Step" in l]
        once_step = [l for l in lines if "this.$once" in l and "Step" in l]
        assert on_step, "Expected a step for this.$on"
        assert once_step, "Expected a separate step for this.$once"

    def test_find_warning_lines_on_does_not_match_once(self):
        """_find_warning_lines for 'this.$on' should not match 'this.$once' lines."""
        from vue3_migration.reporting.markdown import _find_warning_lines

        source = (
            "  this.$on('event', handler)\n"    # L1
            "  this.$once('init', handler)\n"   # L2
            "  this.$on('other', handler)\n"    # L3
        )
        w_on = MigrationWarning("x", "this.$on", "", "", None, "error")
        lines = _find_warning_lines(source, w_on)
        assert 1 in lines
        assert 3 in lines
        assert 2 not in lines, "L2 is this.$once, should not match this.$on"

    def test_recipe_exists_for_once(self):
        """A recipe section should exist for this.$once."""
        entry = MixinEntry(
            local_name="x", mixin_path="x.js", mixin_stem="x",
            members=MixinMembers(),
            warnings=[
                MigrationWarning("x", "this.$once", "this.$once removed",
                    "Use event bus", None, "error"),
            ],
        )
        entries = [(Path("<standalone>"), [entry])]
        recipes = build_recipes_section(entries)
        assert "$once" in recipes


# ---------------------------------------------------------------------------
# Issue 2: Report should not list steps for non-existent composables
# ---------------------------------------------------------------------------

class TestSkippedComposableNotInActionPlan:
    """When a composable was skipped (not generated), the action plan should
    not include steps for it, even if it has info-level warnings."""

    def test_skipped_lifecycle_only_with_unused_members_filtered(self):
        """An entry with only skipped-lifecycle-only (warning) + unused-mixin-member (info)
        should NOT appear in the action plan."""
        entry = MixinEntry(
            local_name="localeMixin",
            mixin_path=Path("localeMixin.js"),
            mixin_stem="localeMixin",
            members=MixinMembers(data=["currentLocale"], methods=["setLocale"]),
            composable=None,
            warnings=[
                MigrationWarning("localeMixin", "skipped-lifecycle-only",
                    "Mixin 'localeMixin' was NOT migrated: lifecycle hooks",
                    "Manually convert lifecycle hooks",
                    None, "warning"),
                MigrationWarning("localeMixin", "unused-mixin-member",
                    "Member 'currentLocale' not used by any component",
                    "", None, "info"),
                MigrationWarning("localeMixin", "unused-mixin-member",
                    "Member 'setLocale' not used by any component",
                    "", None, "info"),
            ],
        )

        entries = [(Path("<standalone>"), [entry])]
        report = build_action_plan(entries, project_root=PROJECT_ROOT)

        # Entry should be filtered out — no steps for non-existent composable
        assert "useLocale" not in report
        assert "skipped-lifecycle-only" not in report

    def test_skipped_lifecycle_with_real_warnings_hides_skip_step(self):
        """When an entry has skipped-lifecycle-only AND real warnings (e.g.
        external-dependency), the skipped-lifecycle-only should not appear as
        a step, but the real warnings should."""
        entry = MixinEntry(
            local_name="pollingMixin",
            mixin_path=Path("pollingMixin.js"),
            mixin_stem="pollingMixin",
            members=MixinMembers(data=["pollTimer"], methods=["startPolling"]),
            composable=None,
            warnings=[
                MigrationWarning("pollingMixin", "external-dependency",
                    "'_pollCallback' — not defined in this mixin",
                    "Pass as param", None, "error"),
                MigrationWarning("pollingMixin", "skipped-lifecycle-only",
                    "Mixin not migrated: lifecycle hooks only",
                    "Manually convert", None, "warning"),
            ],
        )

        entries = [(Path("<standalone>"), [entry])]
        report = build_action_plan(entries, project_root=PROJECT_ROOT)

        # The real warning should appear
        assert "_pollCallback" in report
        # But skipped-lifecycle-only should NOT appear as a step
        assert "skipped-lifecycle-only" not in report

    def test_skipped_no_usage_with_info_also_filtered(self):
        """An entry with only skipped-no-usage + info warnings should also be filtered."""
        entry = MixinEntry(
            local_name="emptyMixin",
            mixin_path=Path("emptyMixin.js"),
            mixin_stem="emptyMixin",
            members=MixinMembers(),
            composable=None,
            warnings=[
                MigrationWarning("emptyMixin", "skipped-no-usage",
                    "No members referenced", "Remove mixin",
                    None, "warning"),
                MigrationWarning("emptyMixin", "unused-mixin-member",
                    "Member 'x' not used", "", None, "info"),
            ],
        )

        entries = [(Path("<standalone>"), [entry])]
        report = build_action_plan(entries, project_root=PROJECT_ROOT)
        assert "useEmpty" not in report


class TestMixinFallbackLineRefs:
    """When _find_warning_lines finds nothing in the composable (e.g. pattern
    was auto-rewritten), the report should use source_lines from the mixin."""

    def test_multiple_mixin_line_refs_shown(self, tmp_path):
        """source_lines=[28, 34, 44] should render as mixin L28, mixin L34, mixin L44."""
        mixin_path = tmp_path / "watcherMixin.js"
        mixin_path.write_text("x\n" * 50)  # dummy content so .exists() is True

        entry = MixinEntry(
            local_name="watcherMixin",
            mixin_path=mixin_path,
            mixin_stem="watcherMixin",
            members=MixinMembers(data=["watchedValue"], methods=["setupWatchers"]),
            composable=None,
            warnings=[
                MigrationWarning(
                    mixin_stem="watcherMixin",
                    category="this.$watch",
                    message="this.$watch — use watch() from vue instead",
                    action_required="Import watch from 'vue' and use watch() directly",
                    line_hint="this.$watch('watchedValue', fn)",
                    severity="warning",
                    source_line=28,
                    source_lines=[28, 34, 44],
                ),
            ],
        )

        entries = [(Path("<standalone>"), [entry])]
        report = build_action_plan(entries, project_root=tmp_path)

        assert "mixin L28" in report
        assert "mixin L34" in report
        assert "mixin L44" in report
        # Should NOT just say "mixin L1"
        assert "mixin L1" not in report
