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


def test_lifecycle_hooks_component_has_on_mounted(project):
    plan = _run(project)
    lh = next((c for c in plan.component_changes if "LifecycleHooks" in str(c.file_path)), None)
    assert lh is not None
    assert "onMounted" in lh.new_content


def test_no_composable_component_gets_generated_composable(project):
    """auto-migrate generates useAuth.js and injects it into NoComposable.vue."""
    plan = _run(project)
    auth = next((c for c in plan.composable_changes if "useAuth" in str(c.file_path)), None)
    assert auth is not None and auth.has_changes
    assert "export function useAuth" in auth.new_content
    no_comp = next((c for c in plan.component_changes if "NoComposable" in str(c.file_path)), None)
    assert no_comp is not None and no_comp.has_changes
    assert "useAuth" in no_comp.new_content


def test_write_all_changes_removes_mixins(project):
    plan = _run(project)
    for change in plan.all_changes:
        if change.has_changes:
            change.file_path.write_text(change.new_content)
    fc_content = next(
        f for f in (project / "src" / "components").rglob("FullyCovered.vue")
    ).read_text()
    assert "mixins:" not in fc_content
    assert "useSelection" in fc_content


def test_all_changes_are_filechange_instances(project):
    plan = _run(project)
    for c in plan.all_changes:
        assert hasattr(c, "file_path")
        assert hasattr(c, "new_content")
        assert hasattr(c, "original_content")
