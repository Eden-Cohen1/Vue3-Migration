"""End-to-end integration test for the full auto-migrate pipeline.

Uses a copy of the dummy_project in tmp_path to allow safe file writes.
"""
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from vue3_migration.models import MigrationConfig
from vue3_migration.workflows.auto_migrate_workflow import run, MigrationPlan

DUMMY = Path(__file__).parent / "fixtures" / "dummy_project"


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "project"
    shutil.copytree(DUMMY, dest)
    return dest


def _run(project):
    with patch("builtins.print"):
        return run(project, MigrationConfig(project_root=project))


def test_returns_migration_plan(project):
    plan = _run(project)
    assert isinstance(plan, MigrationPlan)
    assert plan.has_changes


def test_pagination_composable_patched_for_reset_pagination(project):
    plan = _run(project)
    pagination_change = next(
        (c for c in plan.composable_changes if "usePagination" in str(c.file_path)), None
    )
    assert pagination_change is not None and pagination_change.has_changes
    assert "resetPagination" in pagination_change.new_content


def test_fully_covered_component_migrated(project):
    plan = _run(project)
    fc = next((c for c in plan.component_changes if "FullyCovered" in str(c.file_path)), None)
    assert fc is not None and fc.has_changes
    assert "useSelection" in fc.new_content
    assert "setup()" in fc.new_content
    assert "selectionMixin" not in fc.new_content


def test_lifecycle_hooks_patched_into_composable(project):
    """Lifecycle hooks are patched into the composable, not in the component."""
    plan = _run(project)
    logging = next((c for c in plan.composable_changes if "useLogging" in str(c.file_path)), None)
    assert logging is not None
    assert logging.has_changes
    assert "onMounted(" in logging.new_content
    assert "onBeforeUnmount(" in logging.new_content
    # Component should NOT have lifecycle hooks
    lh = next((c for c in plan.component_changes
               if str(c.file_path).endswith("LifecycleHooks.vue")
               and "All" not in str(c.file_path)), None)
    assert lh is not None
    assert "onMounted" not in lh.new_content


def test_no_composable_component_gets_generated_composable(project):
    """auto-migrate generates useNotification.js and injects it into NoComposable.vue."""
    plan = _run(project)
    notif = next((c for c in plan.composable_changes if "useNotification" in str(c.file_path)), None)
    assert notif is not None and notif.has_changes
    assert "export function useNotification" in notif.new_content
    no_comp = next((c for c in plan.component_changes if "NoComposable" in str(c.file_path)), None)
    assert no_comp is not None and no_comp.has_changes
    assert "useNotification" in no_comp.new_content


def test_write_all_changes_removes_mixins(project):
    plan = _run(project)
    for change in plan.all_changes:
        if change.has_changes:
            change.file_path.write_text(change.new_content, encoding="utf-8")
    fc_content = next(
        f for f in (project / "src" / "components").rglob("FullyCovered.vue")
    ).read_text(encoding="utf-8")
    assert "mixins:" not in fc_content
    assert "useSelection" in fc_content


def test_all_changes_are_filechange_instances(project):
    plan = _run(project)
    for c in plan.all_changes:
        assert hasattr(c, "file_path")
        assert hasattr(c, "new_content")
        assert hasattr(c, "original_content")


def test_lifecycle_hooks_component_has_composable_import(project):
    """LifecycleHooks.vue must have import { useLogging } even when members
    are only referenced through lifecycle hooks, not directly in template."""
    plan = _run(project)
    lh = next((c for c in plan.component_changes
               if str(c.file_path).endswith("LifecycleHooks.vue")
               and "All" not in str(c.file_path)), None)
    assert lh is not None
    assert "import { useLogging }" in lh.new_content


def test_fuzzy_match_component_has_composable_import(project):
    """FuzzyMatch.vue must have import { useAdvancedFilter } for fuzzy-matched composable."""
    plan = _run(project)
    fm = next((c for c in plan.component_changes if "FuzzyMatch" in str(c.file_path)), None)
    assert fm is not None
    assert "import { useAdvancedFilter }" in fm.new_content


def test_multi_mixin_has_all_composable_imports(project):
    """MultiMixin.vue must import all 4 composables including useLogging."""
    plan = _run(project)
    mm = next((c for c in plan.component_changes if "MultiMixin" in str(c.file_path)), None)
    assert mm is not None
    for fn_name in ["useSelection", "usePagination", "useAuth", "useLogging"]:
        assert f"import {{ {fn_name} }}" in mm.new_content, f"Missing import for {fn_name}"


def test_lifecycle_hooks_not_in_component_vue_imports(project):
    """LifecycleHooks.vue should not import lifecycle hooks from vue (they're in the composable)."""
    plan = _run(project)
    lh = next((c for c in plan.component_changes
               if str(c.file_path).endswith("LifecycleHooks.vue")
               and "All" not in str(c.file_path)), None)
    assert lh is not None
    for hook_import in ["onMounted", "onBeforeUnmount", "onBeforeMount"]:
        assert hook_import not in lh.new_content, f"{hook_import} should not be in component"


def test_overridden_members_excluded_from_setup_destructure(project):
    """WithOverrides.vue overrides selectionMode and clearSelection — these
    should NOT appear in the setup() destructure from useSelection()."""
    plan = _run(project)
    wo = next((c for c in plan.component_changes if "WithOverrides" in str(c.file_path)), None)
    assert wo is not None
    # Find the destructure line
    setup_line = next(
        (l for l in wo.new_content.splitlines()
         if "useSelection" in l and "const {" in l),
        None
    )
    assert setup_line is not None, "Expected const { ... } = useSelection() in setup()"
    assert "selectionMode" not in setup_line, "selectionMode is overridden, should not be destructured"
    assert "clearSelection" not in setup_line, "clearSelection is overridden, should not be destructured"


def test_entries_by_component_populated(project):
    """MigrationPlan.entries_by_component should be populated with mixin entries."""
    plan = _run(project)
    assert plan.entries_by_component, "entries_by_component should not be empty"
    for comp_path, entries in plan.entries_by_component:
        assert comp_path.suffix == ".vue" or str(comp_path) == "<standalone>"
        assert len(entries) > 0


def test_template_members_all_in_setup_destructure(project):
    """TemplateMemberTest.vue — all mixin members used in template must appear
    in setup() destructuring and return. Reproduces Bug 4.

    The composable (useLoading.js) defines all members but only returns 4 of 10,
    so the entry starts as BLOCKED_NOT_RETURNED. The patcher adds the missing
    return keys. Re-classification must then make ALL template-used members
    injectable. (Bug 4 was caused by Bug 1 corrupting the composable output,
    which cascaded into incomplete re-classification.)
    """
    plan = _run(project)
    # Verify the composable was patched (not_returned members added)
    loading_patch = next(
        (c for c in plan.composable_changes if "useLoading" in str(c.file_path)), None
    )
    assert loading_patch is not None and loading_patch.has_changes, \
        "useLoading should be patched to add missing return keys"

    tm = next((c for c in plan.component_changes if "TemplateMemberTest" in str(c.file_path)), None)
    assert tm is not None and tm.has_changes
    content = tm.new_content
    # All these members are used in the template and exist in useLoading
    for member in ["isLoading", "loadingMessage", "hasError", "error", "canRetry", "retry"]:
        assert member in content, f"'{member}' should be in migrated component"
    # Check they're in the destructure line specifically
    setup_line = next(
        (l for l in content.splitlines() if "useLoading" in l and "const {" in l),
        None
    )
    assert setup_line is not None, "Expected const { ... } = useLoading() in setup()"
    for member in ["isLoading", "hasError", "error", "canRetry", "retry"]:
        assert member in setup_line, f"'{member}' missing from useLoading() destructure"
