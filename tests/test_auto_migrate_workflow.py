# tests/test_auto_migrate_workflow.py
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from vue3_migration.models import MigrationConfig
from vue3_migration.workflows.auto_migrate_workflow import (
    MigrationPlan,
    collect_all_mixin_entries,
    plan_composable_patches,
    plan_component_injections,
    run,
)

DUMMY = Path(__file__).parent / "fixtures" / "dummy_project"

@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(DUMMY, dest)
    return dest

def _make_config(root):
    return MigrationConfig(project_root=root)

def test_collect_entries_finds_components(project):
    with patch("builtins.print"):
        entries = collect_all_mixin_entries(project, _make_config(project))
    paths = [p.name for p, _ in entries]
    assert "FullyCovered.vue" in paths

def test_run_returns_migration_plan(project):
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    assert isinstance(plan, MigrationPlan)

def test_run_has_changes(project):
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    assert plan.has_changes

def test_composable_patched_for_not_returned(project):
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    pagination = next(
        (c for c in plan.composable_changes if "usePagination" in str(c.file_path)), None
    )
    assert pagination is not None
    assert "resetPagination" in pagination.new_content

def test_fully_covered_component_injected(project):
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    fc = next(
        (c for c in plan.component_changes if "FullyCovered" in str(c.file_path)), None
    )
    assert fc is not None and fc.has_changes
    assert "useSelection" in fc.new_content
    assert "setup()" in fc.new_content

def test_no_composable_component_not_injected(project):
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    no_comp = [c for c in plan.component_changes if "NoComposable" in str(c.file_path)]
    assert all(not c.has_changes for c in no_comp)

def test_lifecycle_hooks_converted(project):
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    lh = next(
        (c for c in plan.component_changes if "LifecycleHooks" in str(c.file_path)), None
    )
    assert lh is not None
    assert "onMounted" in lh.new_content

def test_no_file_io_during_run(project):
    """run() must not write any files."""
    import os
    mtimes = {str(f): os.path.getmtime(f) for f in project.rglob("*.vue")}
    with patch("builtins.print"):
        run(project, _make_config(project))
    for path, t in mtimes.items():
        assert os.path.getmtime(path) == t
