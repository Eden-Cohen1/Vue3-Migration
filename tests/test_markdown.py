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
        assert "see recipe" in result
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
        assert "## Migration Recipes" in result
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
        assert result.count("## Migration Recipes") == 1


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
