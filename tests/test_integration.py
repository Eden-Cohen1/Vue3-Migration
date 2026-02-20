"""Integration tests — end-to-end analysis pipeline against the dummy fixture project.

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
# Edge case 1 — FullyCovered.vue + selectionMixin -> READY
# All mixin members are returned by the composable; nothing blocked.
# ===========================================================================

class TestFullyCovered:
    def test_status_is_ready(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        assert entry.status == MigrationStatus.READY

    def test_composable_matched(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useSelection"

    def test_import_path_uses_at_alias(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        assert entry.composable.import_path == "@/composables/useSelection"

    def test_no_truly_missing(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        assert entry.classification.truly_not_returned == []

    def test_no_overrides(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        assert entry.classification.overridden == []

    def test_used_members_detected_from_template(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        # Template: selectionCount, clearSelection, hasSelection, selectedItems, toggleItem
        assert "selectionCount" in entry.used_members
        assert "clearSelection" in entry.used_members
        assert "hasSelection" in entry.used_members

    def test_injectable_members_match_used(self):
        entry = _run("FullyCovered.vue", "selectionMixin")
        # With no overrides, injectable == used_members
        assert set(entry.classification.injectable) == set(entry.used_members)


# ===========================================================================
# Edge case 2 — WithOverrides.vue + selectionMixin -> READY with overrides
# Component redefines clearSelection (method). useSelection still covers it,
# so clearSelection is NOT in "overridden" (composable isn't missing it).
# The component's version will just shadow it — that's fine for READY status.
# ===========================================================================

class TestWithOverrides:
    def test_status_is_ready(self):
        entry = _run("WithOverrides.vue", "selectionMixin")
        assert entry.status == MigrationStatus.READY

    def test_no_truly_missing(self):
        entry = _run("WithOverrides.vue", "selectionMixin")
        assert entry.classification.truly_missing == []

    def test_no_truly_not_returned(self):
        entry = _run("WithOverrides.vue", "selectionMixin")
        assert entry.classification.truly_not_returned == []

    def test_composable_still_found(self):
        entry = _run("WithOverrides.vue", "selectionMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useSelection"

    def test_selectionCount_is_injectable(self):
        entry = _run("WithOverrides.vue", "selectionMixin")
        # selectionCount is used and NOT overridden by the component
        assert "selectionCount" in entry.classification.injectable


# ===========================================================================
# Edge case 3a — PartiallyBlocked.vue + paginationMixin -> BLOCKED_MISSING_MEMBERS
# hasPrevPage and prevPage are completely absent from usePagination.
# ===========================================================================

class TestPartiallyBlockedPagination:
    def test_status_is_blocked_missing(self):
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert entry.status == MigrationStatus.BLOCKED_MISSING_MEMBERS

    def test_composable_found(self):
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "usePagination"

    def test_hasprevpage_is_truly_missing(self):
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert "hasPrevPage" in entry.classification.truly_missing

    def test_prevpage_is_truly_missing(self):
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert "prevPage" in entry.classification.truly_missing

    def test_reset_pagination_in_all_identifiers(self):
        # resetPagination IS defined in the composable (just not returned)
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert "resetPagination" in entry.composable.all_identifiers

    def test_reset_pagination_not_in_return_keys(self):
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert "resetPagination" not in entry.composable.return_keys

    def test_reset_pagination_not_a_blocker_here(self):
        # resetPagination is not USED by this component, so it's not in truly_not_returned
        entry = _run("PartiallyBlocked.vue", "paginationMixin")
        assert "resetPagination" not in entry.used_members
        assert "resetPagination" not in entry.classification.truly_not_returned


# ===========================================================================
# Edge case 3b — PartiallyBlocked.vue + selectionMixin -> READY
# Two mixins in one component — one is blocked, the other is fine independently.
# ===========================================================================

class TestPartiallyBlockedSelection:
    def test_status_is_ready(self):
        entry = _run("PartiallyBlocked.vue", "selectionMixin")
        assert entry.status == MigrationStatus.READY

    def test_selectioncount_used(self):
        entry = _run("PartiallyBlocked.vue", "selectionMixin")
        assert "selectionCount" in entry.used_members


# ===========================================================================
# Edge case 4 — NoComposable.vue + authMixin -> BLOCKED_NO_COMPOSABLE
# No composable exists; user answers "n" when asked.
# ===========================================================================

class TestNoComposable:
    def test_status_is_blocked_no_composable(self):
        entry = _run("NoComposable.vue", "authMixin", mock_input="n")
        assert entry.status == MigrationStatus.BLOCKED_NO_COMPOSABLE

    def test_composable_is_none(self):
        entry = _run("NoComposable.vue", "authMixin", mock_input="n")
        assert entry.composable is None

    def test_classification_is_none(self):
        entry = _run("NoComposable.vue", "authMixin", mock_input="n")
        assert entry.classification is None

    def test_mixin_members_still_extracted(self):
        entry = _run("NoComposable.vue", "authMixin", mock_input="n")
        assert "isAuthenticated" in entry.members.data
        assert "currentUser" in entry.members.data
        assert "logout" in entry.members.methods

    def test_lifecycle_hooks_still_extracted(self):
        entry = _run("NoComposable.vue", "authMixin", mock_input="n")
        assert "created" in entry.lifecycle_hooks

    def test_used_members_still_detected(self):
        entry = _run("NoComposable.vue", "authMixin", mock_input="n")
        assert "isAuthenticated" in entry.used_members
        assert "logout" in entry.used_members


# ===========================================================================
# Edge case 5 — LifecycleHooks.vue + loggingMixin -> READY
# loggingMixin has created/mounted/beforeDestroy hooks; useLogging covers
# data+methods. Hooks are reported but do NOT block injection.
# ===========================================================================

class TestLifecycleHooks:
    def test_status_is_ready(self):
        entry = _run("LifecycleHooks.vue", "loggingMixin")
        assert entry.status == MigrationStatus.READY

    def test_three_lifecycle_hooks_extracted(self):
        entry = _run("LifecycleHooks.vue", "loggingMixin")
        assert "created" in entry.lifecycle_hooks
        assert "mounted" in entry.lifecycle_hooks
        assert "beforeDestroy" in entry.lifecycle_hooks

    def test_composable_covers_data_and_methods(self):
        entry = _run("LifecycleHooks.vue", "loggingMixin")
        assert entry.classification.truly_missing == []
        assert entry.classification.truly_not_returned == []

    def test_composable_matched(self):
        entry = _run("LifecycleHooks.vue", "loggingMixin")
        assert entry.composable.fn_name == "useLogging"

    def test_used_members(self):
        entry = _run("LifecycleHooks.vue", "loggingMixin")
        assert "logs" in entry.used_members
        assert "log" in entry.used_members


# ===========================================================================
# Edge case 6 — FuzzyMatch.vue + filterMixin -> READY via FUZZY match
# Candidates = ['useFilter'], no exact match, but 'filter' IS a substring
# of 'useAdvancedFilter' -> fuzzy hit.
# ===========================================================================

class TestFuzzyMatch:
    def test_composable_found_via_fuzzy(self):
        entry = _run("FuzzyMatch.vue", "filterMixin")
        assert entry.composable is not None
        assert entry.composable.fn_name == "useAdvancedFilter"

    def test_status_is_ready(self):
        entry = _run("FuzzyMatch.vue", "filterMixin")
        assert entry.status == MigrationStatus.READY

    def test_all_members_covered(self):
        entry = _run("FuzzyMatch.vue", "filterMixin")
        assert entry.classification.truly_missing == []
        assert entry.classification.truly_not_returned == []

    def test_used_members_from_template(self):
        entry = _run("FuzzyMatch.vue", "filterMixin")
        assert "filterText" in entry.used_members
        assert "filteredCount" in entry.used_members
        assert "clearFilter" in entry.used_members
        assert "applyFilter" in entry.used_members


# ===========================================================================
# Edge case 7 — NotReturnedBlocker.vue + paginationMixin -> BLOCKED_NOT_RETURNED
# Component uses resetPagination, which IS defined in usePagination but
# is intentionally excluded from its return statement.
# ===========================================================================

class TestNotReturnedBlocker:
    def test_status_is_blocked_not_returned(self):
        entry = _run("NotReturnedBlocker.vue", "paginationMixin")
        assert entry.status == MigrationStatus.BLOCKED_NOT_RETURNED

    def test_reset_pagination_is_truly_not_returned(self):
        entry = _run("NotReturnedBlocker.vue", "paginationMixin")
        assert "resetPagination" in entry.classification.truly_not_returned

    def test_reset_pagination_in_all_identifiers(self):
        entry = _run("NotReturnedBlocker.vue", "paginationMixin")
        assert "resetPagination" in entry.composable.all_identifiers

    def test_reset_pagination_not_in_return_keys(self):
        entry = _run("NotReturnedBlocker.vue", "paginationMixin")
        assert "resetPagination" not in entry.composable.return_keys

    def test_current_page_is_injectable(self):
        # currentPage IS returned and used -> injectable
        entry = _run("NotReturnedBlocker.vue", "paginationMixin")
        assert "currentPage" in entry.classification.injectable

    def test_no_truly_missing(self):
        # resetPagination exists in the composable — it's just not returned
        entry = _run("NotReturnedBlocker.vue", "paginationMixin")
        assert "resetPagination" not in entry.classification.truly_missing


# ===========================================================================
# Edge case 8 — OverrideUnblocksComp.vue + paginationMixin -> READY
# usePagination is MISSING hasPrevPage and prevPage, BUT the component
# defines them itself -> classification.overridden -> truly_missing = [] -> READY
# ===========================================================================

class TestOverrideUnblocksComp:
    def test_status_is_ready(self):
        entry = _run("OverrideUnblocksComp.vue", "paginationMixin")
        assert entry.status == MigrationStatus.READY

    def test_hasprevpage_is_overridden_not_truly_missing(self):
        entry = _run("OverrideUnblocksComp.vue", "paginationMixin")
        assert "hasPrevPage" in entry.classification.overridden
        assert "hasPrevPage" not in entry.classification.truly_missing

    def test_prevpage_is_overridden_not_truly_missing(self):
        entry = _run("OverrideUnblocksComp.vue", "paginationMixin")
        assert "prevPage" in entry.classification.overridden
        assert "prevPage" not in entry.classification.truly_missing

    def test_truly_missing_is_empty(self):
        entry = _run("OverrideUnblocksComp.vue", "paginationMixin")
        assert entry.classification.truly_missing == []

    def test_overridden_members_not_in_injectable(self):
        # Overridden members are provided by the component, not by the composable
        entry = _run("OverrideUnblocksComp.vue", "paginationMixin")
        assert "hasPrevPage" not in entry.classification.injectable
        assert "prevPage" not in entry.classification.injectable

    def test_returned_members_are_injectable(self):
        entry = _run("OverrideUnblocksComp.vue", "paginationMixin")
        # nextPage and hasNextPage are returned by usePagination and used by the component
        assert "nextPage" in entry.classification.injectable
        assert "hasNextPage" in entry.classification.injectable
