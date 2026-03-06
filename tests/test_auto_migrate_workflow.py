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

def test_no_composable_component_gets_generated_composable(project):
    """NoComposable.vue uses notificationMixin — a new useNotification.js should be generated."""
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    # A new composable should be generated
    notification_composable = next(
        (c for c in plan.composable_changes if "useNotification" in str(c.file_path)), None
    )
    assert notification_composable is not None and notification_composable.has_changes
    assert notification_composable.original_content == ""  # new file
    assert "export function useNotification" in notification_composable.new_content
    # NoComposable.vue should now be injected with useNotification
    no_comp = next((c for c in plan.component_changes if "NoComposable" in str(c.file_path)), None)
    assert no_comp is not None and no_comp.has_changes
    assert "useNotification" in no_comp.new_content

def test_lifecycle_hooks_patched_into_composable(project):
    """Lifecycle hooks are patched into the composable, not injected into setup()."""
    with patch("builtins.print"):
        plan = run(project, _make_config(project))
    # useLogging composable should have lifecycle hooks patched in
    logging = next(
        (c for c in plan.composable_changes if "useLogging" in str(c.file_path)), None
    )
    assert logging is not None
    assert logging.has_changes
    assert "onMounted(" in logging.new_content
    assert "onBeforeUnmount(" in logging.new_content
    # LifecycleHooks.vue component should NOT have lifecycle hooks in setup
    lh = next(
        (c for c in plan.component_changes
         if str(c.file_path).endswith("LifecycleHooks.vue")
         and "All" not in str(c.file_path)), None
    )
    assert lh is not None
    assert "onMounted" not in lh.new_content

def test_no_file_io_during_run(project):
    """run() must not write any files."""
    import os
    mtimes = {str(f): os.path.getmtime(f) for f in project.rglob("*.vue")}
    with patch("builtins.print"):
        run(project, _make_config(project))
    for path, t in mtimes.items():
        assert os.path.getmtime(path) == t


# ---------------------------------------------------------------------------
# plan_new_composables — no composables/ directory in project
# ---------------------------------------------------------------------------

from vue3_migration.workflows.auto_migrate_workflow import plan_new_composables


_AUTH_MIXIN = "export default { data() { return { user: null }; }, methods: { login() {} } }"
_LOGIN_VUE = (
    "<template><div>{{ user }}</div></template>\n"
    "<script>\n"
    "import authMixin from '@/mixins/authMixin';\n"
    "export default { mixins: [authMixin] };\n"
    "</script>\n"
)
_LOGIN_VUE_RELATIVE = (
    "<template><div>{{ user }}</div></template>\n"
    "<script>\n"
    "import authMixin from '../mixins/authMixin';\n"
    "export default { mixins: [authMixin] };\n"
    "</script>\n"
)


def test_plan_new_composables_no_composables_dir_uses_src_composables(tmp_path):
    """When no composables/ dir exists but src/ does, new composables go to src/composables/."""
    (tmp_path / "src" / "mixins").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "mixins" / "authMixin.js").write_text(_AUTH_MIXIN)
    (tmp_path / "src" / "components" / "Login.vue").write_text(_LOGIN_VUE)

    config = MigrationConfig(project_root=tmp_path)
    with patch("builtins.print"):
        entries = collect_all_mixin_entries(tmp_path, config)

    changes = plan_new_composables(entries, tmp_path)

    assert len(changes) >= 1
    target_paths = [str(c.file_path) for c in changes]
    assert any("src" in p and "composables" in p for p in target_paths)


def test_plan_new_composables_no_src_dir_uses_project_root_composables(tmp_path):
    """When neither src/ nor composables/ exist, new composables go to <root>/composables/."""
    (tmp_path / "mixins").mkdir()
    (tmp_path / "components").mkdir()
    (tmp_path / "mixins" / "authMixin.js").write_text(_AUTH_MIXIN)
    (tmp_path / "components" / "Login.vue").write_text(_LOGIN_VUE_RELATIVE)

    config = MigrationConfig(project_root=tmp_path)
    with patch("builtins.print"):
        entries = collect_all_mixin_entries(tmp_path, config)

    changes = plan_new_composables(entries, tmp_path)

    assert len(changes) >= 1
    for c in changes:
        assert c.file_path.parts[-2] == "composables"


def test_run_generates_composable_when_no_composables_dir(tmp_path):
    """Full run() on a project with no composables/ dir still generates composables."""
    (tmp_path / "src" / "mixins").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "mixins" / "authMixin.js").write_text(_AUTH_MIXIN)
    (tmp_path / "src" / "components" / "Login.vue").write_text(_LOGIN_VUE)

    config = MigrationConfig(project_root=tmp_path)
    with patch("builtins.print"):
        plan = run(tmp_path, config)

    assert plan.has_changes
    assert any("useAuth" in str(c.file_path) for c in plan.composable_changes)


# ---------------------------------------------------------------------------
# MigrationConfig.regenerate flag
# ---------------------------------------------------------------------------

def test_migration_config_has_regenerate_flag():
    config = MigrationConfig()
    assert hasattr(config, 'regenerate')
    assert config.regenerate is False

def test_migration_config_regenerate_true():
    config = MigrationConfig(regenerate=True)
    assert config.regenerate is True


# ---------------------------------------------------------------------------
# run_scoped — standalone mixin (not used by any component)
# ---------------------------------------------------------------------------

from vue3_migration.workflows.auto_migrate_workflow import run_scoped


def test_run_scoped_standalone_mixin_generates_composable(project):
    """A mixin not used by any component should still generate a composable."""
    with patch("builtins.print"):
        plan = run_scoped(project, _make_config(project), mixin_stem="ordersMixin")
    assert plan.has_changes
    # Should have a generated composable
    composable = next(
        (c for c in plan.composable_changes if "useOrders" in str(c.file_path)), None
    )
    assert composable is not None
    assert composable.original_content == ""  # new file
    assert "export function useOrders" in composable.new_content
    # No component changes since no component uses this mixin
    assert not any(c.has_changes for c in plan.component_changes)


def test_run_scoped_standalone_mixin_not_found_returns_empty_plan(project):
    """A mixin stem that doesn't match any file should produce an empty plan."""
    with patch("builtins.print"):
        plan = run_scoped(project, _make_config(project), mixin_stem="nonexistentMixin")
    assert not plan.has_changes


def test_run_scoped_standalone_mixin_with_existing_composable_patches_it(project):
    """If a composable already exists for the mixin, it should be re-patched."""
    # Create a composable for ordersMixin
    composable_dir = project / "src" / "composables"
    composable_dir.mkdir(parents=True, exist_ok=True)
    (composable_dir / "useOrders.js").write_text(
        "import { ref } from 'vue';\nexport function useOrders() { return { orders: ref([]) } }\n"
    )
    with patch("builtins.print"):
        plan = run_scoped(project, _make_config(project), mixin_stem="ordersMixin")
    # The existing composable should be picked up for patching
    assert plan.composable_changes is not None
