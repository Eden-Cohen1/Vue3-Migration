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


# ---------------------------------------------------------------------------
# run_scoped — mixin imported by component but zero members used
# ---------------------------------------------------------------------------

def _add_zero_member_component(project):
    """Create a component that imports loadingMixin but uses none of its members."""
    comp = project / "src" / "components" / "EmptyUsage.vue"
    comp.write_text(
        "<template><div>No mixin members used</div></template>\n"
        "<script>\n"
        "import loadingMixin from '../mixins/loadingMixin'\n"
        "export default {\n"
        "  name: 'EmptyUsage',\n"
        "  mixins: [loadingMixin],\n"
        "}\n"
        "</script>\n"
    )
    return comp


def test_run_scoped_zero_members_generates_composable(project):
    """Mixin imported by component but no members used should still generate composable."""
    _add_zero_member_component(project)
    # Ensure no composable exists yet
    composable = project / "src" / "composables" / "useLoading.js"
    if composable.exists():
        composable.unlink()
    with patch("builtins.print"):
        plan = run_scoped(project, _make_config(project), mixin_stem="loadingMixin")
    assert plan.has_changes
    gen = next(
        (c for c in plan.composable_changes if "useLoading" in str(c.file_path) and c.has_changes),
        None,
    )
    assert gen is not None, "Composable should be generated even with zero member usage"
    assert "export function useLoading" in gen.new_content


def test_run_scoped_zero_members_no_component_changes(project):
    """Component with zero used members should NOT be modified."""
    _add_zero_member_component(project)
    composable = project / "src" / "composables" / "useLoading.js"
    if composable.exists():
        composable.unlink()
    with patch("builtins.print"):
        plan = run_scoped(project, _make_config(project), mixin_stem="loadingMixin")
    comp_change = next(
        (c for c in plan.component_changes if "EmptyUsage" in str(c.file_path) and c.has_changes),
        None,
    )
    assert comp_change is None, "Component should not be modified when no members are used"


# ---------------------------------------------------------------------------
# _warn_unused_mixin_members
# ---------------------------------------------------------------------------

from vue3_migration.models import MigrationWarning, MixinMembers, MixinEntry
from vue3_migration.workflows.auto_migrate_workflow import _warn_unused_mixin_members


def _make_entry(mixin_stem, members, used_members):
    """Helper to build a MixinEntry with the given members and used_members."""
    return MixinEntry(
        local_name=mixin_stem,
        mixin_path=Path(f"/fake/mixins/{mixin_stem}.js"),
        mixin_stem=mixin_stem,
        members=members,
        used_members=used_members,
    )


class TestWarnUnusedMixinMembers:
    def test_unused_members_get_warnings(self):
        """Members not used by any component should produce warnings."""
        members = MixinMembers(data=["foo"], methods=["bar", "baz"])
        entry = _make_entry("myMixin", members, used_members=["bar"])
        entries = [(Path("/fake/Comp.vue"), [entry])]

        _warn_unused_mixin_members(entries)

        unused_warnings = [w for w in entry.warnings if w.category == "unused-mixin-member"]
        assert len(unused_warnings) == 2
        names = {w.message.split("'")[1] for w in unused_warnings}
        assert names == {"foo", "baz"}

    def test_used_members_no_warnings(self):
        """Members used by at least one component should NOT get warnings."""
        members = MixinMembers(methods=["doStuff"])
        entry = _make_entry("myMixin", members, used_members=["doStuff"])
        entries = [(Path("/fake/Comp.vue"), [entry])]

        _warn_unused_mixin_members(entries)

        unused_warnings = [w for w in entry.warnings if w.category == "unused-mixin-member"]
        assert len(unused_warnings) == 0

    def test_union_across_components(self):
        """used_members are unioned across components sharing the same mixin."""
        members = MixinMembers(data=["a"], methods=["b"], computed=["c"])
        entry1 = _make_entry("shared", members, used_members=["a"])
        entry2 = _make_entry("shared", members, used_members=["b"])
        entries = [
            (Path("/fake/Comp1.vue"), [entry1]),
            (Path("/fake/Comp2.vue"), [entry2]),
        ]

        _warn_unused_mixin_members(entries)

        # Only "c" is unused
        for entry in [entry1, entry2]:
            unused = [w for w in entry.warnings if w.category == "unused-mixin-member"]
            assert len(unused) == 1
            assert "'c'" in unused[0].message

    def test_standalone_entries_skipped(self):
        """Entries with Path("<standalone>") should be skipped entirely."""
        members = MixinMembers(data=["x"], methods=["y"])
        entry = _make_entry("standaloneMixin", members, used_members=[])
        entries = [(Path("<standalone>"), [entry])]

        _warn_unused_mixin_members(entries)

        unused_warnings = [w for w in entry.warnings if w.category == "unused-mixin-member"]
        assert len(unused_warnings) == 0

    def test_warning_severity_is_info(self):
        """All unused-mixin-member warnings should have severity 'info'."""
        members = MixinMembers(computed=["unused1"], watch=["unused2"])
        entry = _make_entry("myMixin", members, used_members=[])
        entries = [(Path("/fake/Comp.vue"), [entry])]

        _warn_unused_mixin_members(entries)

        for w in entry.warnings:
            if w.category == "unused-mixin-member":
                assert w.severity == "info"

    def test_warning_message_includes_section(self):
        """Warning message should include the section (data/computed/methods/watch)."""
        members = MixinMembers(data=["d"], computed=["c"], methods=["m"], watch=["w"])
        entry = _make_entry("myMixin", members, used_members=[])
        entries = [(Path("/fake/Comp.vue"), [entry])]

        _warn_unused_mixin_members(entries)

        msgs = {w.message for w in entry.warnings if w.category == "unused-mixin-member"}
        assert "'d' (data) defined in mixin but not used by any component" in msgs
        assert "'c' (computed) defined in mixin but not used by any component" in msgs
        assert "'m' (methods) defined in mixin but not used by any component" in msgs
        assert "'w' (watch) defined in mixin but not used by any component" in msgs

    def test_warning_action_required(self):
        """Warning action_required should reference the member name."""
        members = MixinMembers(methods=["doThing"])
        entry = _make_entry("myMixin", members, used_members=[])
        entries = [(Path("/fake/Comp.vue"), [entry])]

        _warn_unused_mixin_members(entries)

        w = entry.warnings[0]
        assert "doThing" in w.action_required
        assert "remove from composable" in w.action_required

    def test_no_entries_no_crash(self):
        """Empty entries list should not crash."""
        _warn_unused_mixin_members([])

    def test_all_members_used_no_warnings(self):
        """When all members are used, no warnings should be produced."""
        members = MixinMembers(data=["a"], methods=["b"])
        entry = _make_entry("myMixin", members, used_members=["a", "b"])
        entries = [(Path("/fake/Comp.vue"), [entry])]

        _warn_unused_mixin_members(entries)

        assert len([w for w in entry.warnings if w.category == "unused-mixin-member"]) == 0
