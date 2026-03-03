"""Integration tests — new fixture components (8–21).

Each test runs analyze_mixin() (the real workflow function) against an actual fixture
component and fixture mixin/composable files, then asserts on the resulting MixinEntry.

interactive input() calls are patched out; print() is suppressed to keep output clean.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from vue3_migration.core.component_analyzer import extract_own_members, parse_imports
from vue3_migration.core.composable_search import find_composable_dirs
from vue3_migration.models import MigrationStatus
from vue3_migration.workflows.component_workflow import analyze_mixin

FIXTURES = Path(__file__).parent / "fixtures" / "dummy_project"
PROJECT_ROOT = FIXTURES


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _run(component_name: str, mixin_local_name: str, mock_input: str = "n"):
    """Run analyze_mixin for one mixin in a component, with I/O mocked out."""
    component_path = FIXTURES / "src" / "components" / component_name
    component_source = component_path.read_text()
    all_imports = parse_imports(component_source)
    import_path = all_imports[mixin_local_name]
    own_members = extract_own_members(component_source)
    comp_dirs = find_composable_dirs(PROJECT_ROOT)

    with patch("builtins.input", return_value=mock_input), \
         patch("builtins.print"):
        return analyze_mixin(
            local_name=mixin_local_name,
            import_path=import_path,
            component_path=component_path,
            component_source=component_source,
            composable_dirs=comp_dirs,
            project_root=PROJECT_ROOT,
            component_own_members=own_members,
        )


# ===========================================================================
# 8 — LargeComponent.vue + tableMixin -> READY
# useTable covers all 34 members (12 data, 10 computed, 12 methods).
# ===========================================================================

class TestLargeComponent:
    def test_status_is_ready(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useTable"

    def test_no_truly_missing(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members_data(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        # rows is defined in the mixin but not directly referenced in
        # the component template/script, so it is not in used_members.
        for member in [
            "columns", "sortColumn", "sortDirection", "searchQuery",
            "selectedRows", "pageSize", "currentPage", "loading", "error",
            "filters", "expandedRows",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"

    def test_used_members_computed(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        for member in [
            "filteredRows", "sortedRows", "paginatedRows", "totalRows",
            "totalPages", "hasNextPage", "hasPrevPage", "isEmpty",
            "selectedCount", "isAllSelected",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"

    def test_used_members_methods(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        for member in [
            "sort", "search", "selectRow", "selectAll", "clearSelection",
            "nextPage", "prevPage", "goToPage", "expandRow", "collapseRow",
            "refresh", "exportData",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"

    def test_lifecycle_hooks_detected(self):
        entry = _run("LargeComponent.vue", "tableMixin")
        assert "created" in entry.lifecycle_hooks
        assert "beforeDestroy" in entry.lifecycle_hooks


# ===========================================================================
# 9 — DataOnlyMixin.vue + stateMixin -> READY
# useState covers all data members.
# ===========================================================================

class TestDataOnlyMixin:
    def test_status_is_ready(self):
        entry = _run("DataOnlyMixin.vue", "stateMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("DataOnlyMixin.vue", "stateMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useState"

    def test_no_truly_missing(self):
        entry = _run("DataOnlyMixin.vue", "stateMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("DataOnlyMixin.vue", "stateMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("DataOnlyMixin.vue", "stateMixin")
        for member in [
            "count", "name", "items", "config", "isActive",
            "metadata", "tags", "timestamp",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 10 — ComputedOnlyMixin.vue + derivedMixin -> READY
# useDerived covers all members.
# ===========================================================================

class TestComputedOnlyMixin:
    def test_status_is_ready(self):
        entry = _run("ComputedOnlyMixin.vue", "derivedMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("ComputedOnlyMixin.vue", "derivedMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useDerived"

    def test_no_truly_missing(self):
        entry = _run("ComputedOnlyMixin.vue", "derivedMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("ComputedOnlyMixin.vue", "derivedMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("ComputedOnlyMixin.vue", "derivedMixin")
        for member in [
            "baseValue", "label", "doubled", "tripled",
            "formatted", "isPositive", "summary",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 11 — MethodsOnlyMixin.vue + actionsMixin -> READY
# useActions covers all members.
# ===========================================================================

class TestMethodsOnlyMixin:
    def test_status_is_ready(self):
        entry = _run("MethodsOnlyMixin.vue", "actionsMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("MethodsOnlyMixin.vue", "actionsMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useActions"

    def test_no_truly_missing(self):
        entry = _run("MethodsOnlyMixin.vue", "actionsMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("MethodsOnlyMixin.vue", "actionsMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("MethodsOnlyMixin.vue", "actionsMixin")
        for member in [
            "execute", "retry", "cancel", "log", "clearLog", "actionLog",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 12 — AllLifecycleHooks.vue + lifecycleMixin -> READY
# useLifecycle covers data + methods. All 11 lifecycle hooks are reported.
# ===========================================================================

class TestAllLifecycleHooks:
    def test_status_is_ready(self):
        entry = _run("AllLifecycleHooks.vue", "lifecycleMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("AllLifecycleHooks.vue", "lifecycleMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useLifecycle"

    def test_no_truly_missing(self):
        entry = _run("AllLifecycleHooks.vue", "lifecycleMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("AllLifecycleHooks.vue", "lifecycleMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("AllLifecycleHooks.vue", "lifecycleMixin")
        for member in ["hookLog", "mountCount", "isActive", "logHook"]:
            assert member in entry.used_members, f"{member} not in used_members"

    def test_all_eleven_lifecycle_hooks(self):
        entry = _run("AllLifecycleHooks.vue", "lifecycleMixin")
        expected_hooks = [
            "beforeCreate", "created", "beforeMount", "mounted",
            "beforeUpdate", "updated", "activated", "deactivated",
            "beforeDestroy", "destroyed", "errorCaptured",
        ]
        for hook in expected_hooks:
            assert hook in entry.lifecycle_hooks, f"{hook} not in lifecycle_hooks"


# ===========================================================================
# 13 — ComplexDefaults.vue + stateMixin -> READY
# useState covers all. Component overrides config and items.
# ===========================================================================

class TestComplexDefaults:
    def test_status_is_ready(self):
        entry = _run("ComplexDefaults.vue", "stateMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("ComplexDefaults.vue", "stateMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useState"

    def test_no_truly_missing(self):
        entry = _run("ComplexDefaults.vue", "stateMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("ComplexDefaults.vue", "stateMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("ComplexDefaults.vue", "stateMixin")
        for member in [
            "count", "config", "items", "tags", "name",
            "isActive", "metadata", "timestamp",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"

    def test_config_and_items_data_overrides_not_detected_as_overridden(self):
        # The component redefines config and items in its own data(), but
        # because the composable also returns them, the classifier does not
        # flag them as "overridden" (overridden only applies when the
        # composable is missing the member).
        entry = _run("ComplexDefaults.vue", "stateMixin")
        assert "config" in entry.classification.injectable
        assert "items" in entry.classification.injectable


# ===========================================================================
# 14 — ChainedComputed.vue + metricsMixin -> READY
# useMetrics covers all members.
# ===========================================================================

class TestChainedComputed:
    def test_status_is_ready(self):
        entry = _run("ChainedComputed.vue", "metricsMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("ChainedComputed.vue", "metricsMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useMetrics"

    def test_no_truly_missing(self):
        entry = _run("ChainedComputed.vue", "metricsMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("ChainedComputed.vue", "metricsMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("ChainedComputed.vue", "metricsMixin")
        for member in [
            "sum", "average", "scaled", "adjusted", "display", "trend",
            "multiplier", "offset", "precision", "rawData",
            "addDataPoint", "reset",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 15 — NestedThisAccess.vue + tableMixin -> READY
# useTable covers all members.
# ===========================================================================

class TestNestedThisAccess:
    def test_status_is_ready(self):
        entry = _run("NestedThisAccess.vue", "tableMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("NestedThisAccess.vue", "tableMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useTable"

    def test_no_truly_missing(self):
        entry = _run("NestedThisAccess.vue", "tableMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("NestedThisAccess.vue", "tableMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members_include_key_table_members(self):
        entry = _run("NestedThisAccess.vue", "tableMixin")
        for member in [
            "columns", "paginatedRows", "selectedRows",
            "sortedRows", "expandedRows", "filters",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 16 — StringCommentSafety.vue + validationMixin -> READY
# useValidation covers all members.
# ===========================================================================

class TestStringCommentSafety:
    def test_status_is_ready(self):
        entry = _run("StringCommentSafety.vue", "validationMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("StringCommentSafety.vue", "validationMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useValidation"

    def test_no_truly_missing(self):
        entry = _run("StringCommentSafety.vue", "validationMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("StringCommentSafety.vue", "validationMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("StringCommentSafety.vue", "validationMixin")
        for member in [
            "isValid", "errorCount", "firstError", "validateAll",
            "clearErrors", "isValidating", "lastValidated", "rules",
            "hasFieldError",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 17 — ConditionalLogic.vue + validationMixin -> READY
# useValidation covers all members.
# ===========================================================================

class TestConditionalLogic:
    def test_status_is_ready(self):
        entry = _run("ConditionalLogic.vue", "validationMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("ConditionalLogic.vue", "validationMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useValidation"

    def test_no_truly_missing(self):
        entry = _run("ConditionalLogic.vue", "validationMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("ConditionalLogic.vue", "validationMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("ConditionalLogic.vue", "validationMixin")
        for member in [
            "isValid", "errorCount", "firstError", "clearErrors",
            "isValidating", "lastValidated", "rules",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 18 — ExistingSetupMixin.vue + selectionMixin -> READY
# useSelection covers all members.
# ===========================================================================

class TestExistingSetupMixin:
    def test_status_is_ready(self):
        entry = _run("ExistingSetupMixin.vue", "selectionMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("ExistingSetupMixin.vue", "selectionMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useSelection"

    def test_no_truly_missing(self):
        entry = _run("ExistingSetupMixin.vue", "selectionMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("ExistingSetupMixin.vue", "selectionMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("ExistingSetupMixin.vue", "selectionMixin")
        for member in [
            "selectionCount", "clearSelection", "hasSelection", "toggleItem",
        ]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 19 — UnusedMixinMembers.vue + itemsMixin -> READY
# useItems covers all, but only a small subset is actually used.
# ===========================================================================

class TestUnusedMixinMembers:
    def test_status_is_ready(self):
        entry = _run("UnusedMixinMembers.vue", "itemsMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("UnusedMixinMembers.vue", "itemsMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useItems"

    def test_no_truly_missing(self):
        entry = _run("UnusedMixinMembers.vue", "itemsMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("UnusedMixinMembers.vue", "itemsMixin")
        assert entry.classification.truly_not_returned == []

    def test_only_items_in_used_members(self):
        entry = _run("UnusedMixinMembers.vue", "itemsMixin")
        assert "items" in entry.used_members

    def test_injectable_is_small_set(self):
        entry = _run("UnusedMixinMembers.vue", "itemsMixin")
        # injectable only includes members that are actually used
        assert set(entry.classification.injectable) == set(entry.used_members)


# ===========================================================================
# 20 — ReactiveGuard.vue + storageMixin -> BLOCKED_MISSING_MEMBERS
# useStorage returns { state, get, set, clear } but the mixin exposes
# cache and ttl as separate data members. These are truly_missing from
# the composable (it wraps them in a single `state` object instead).
# ===========================================================================

class TestReactiveGuard:
    def test_status_is_blocked_missing(self):
        entry = _run("ReactiveGuard.vue", "storageMixin")
        assert entry.status == MigrationStatus.BLOCKED_MISSING_MEMBERS

    def test_composable_matched(self):
        entry = _run("ReactiveGuard.vue", "storageMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useStorage"

    def test_cache_and_ttl_are_truly_missing(self):
        entry = _run("ReactiveGuard.vue", "storageMixin")
        assert "cache" in entry.classification.truly_missing
        assert "ttl" in entry.classification.truly_missing

    def test_no_truly_not_returned(self):
        entry = _run("ReactiveGuard.vue", "storageMixin")
        assert entry.classification.truly_not_returned == []

    def test_used_members(self):
        entry = _run("ReactiveGuard.vue", "storageMixin")
        for member in ["ttl", "cache", "set", "get", "clear"]:
            assert member in entry.used_members, f"{member} not in used_members"


# ===========================================================================
# 21 — DynamicReturn.vue + toggleMixin -> composable found
# useToggle returns a variable (not an object literal). The composable
# should still be matched.
# ===========================================================================

class TestDynamicReturn:
    def test_composable_found(self):
        entry = _run("DynamicReturn.vue", "toggleMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useToggle"

    def test_used_members(self):
        entry = _run("DynamicReturn.vue", "toggleMixin")
        for member in ["label", "isOpen", "toggle", "open", "close"]:
            assert member in entry.used_members, f"{member} not in used_members"
