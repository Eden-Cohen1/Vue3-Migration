"""End-to-end integration test for the full auto-migrate pipeline.

Uses a copy of the dummy_project in tmp_path to allow safe file writes.
"""
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from vue3_migration.models import MigrationConfig, MixinEntry, MixinMembers
from vue3_migration.workflows.auto_migrate_workflow import (
    run, MigrationPlan,
    _inject_setup_external_dep_warnings, _format_setup_warning,
)

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


def test_vue_lifecycle_imports_consolidated(project):
    """Components with multiple lifecycle hooks should have a single `from 'vue'` import."""
    plan = _run(project)
    lh = next((c for c in plan.component_changes
               if str(c.file_path).endswith("LifecycleHooks.vue")
               and "All" not in str(c.file_path)), None)
    assert lh is not None
    vue_imports = [l for l in lh.new_content.splitlines() if "from 'vue'" in l]
    assert len(vue_imports) == 1, f"Expected 1 vue import line, got {len(vue_imports)}: {vue_imports}"


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


# ---------------------------------------------------------------------------
# External dependency setup() warning tests
# ---------------------------------------------------------------------------

def _make_entry(stem, data=None, computed=None, methods=None, watch=None):
    return MixinEntry(
        local_name=stem,
        mixin_path=Path(f"/fake/{stem}.js"),
        mixin_stem=stem,
        members=MixinMembers(
            data=data or [], computed=computed or [],
            methods=methods or [], watch=watch or [],
        ),
    )


class TestFormatSetupWarning:
    def test_sibling_source(self):
        entry = _make_entry("commentMixin", methods=["loadComments"])
        src = {"kind": "sibling", "detail": "loadingMixin.data", "sources": ["loadingMixin.data"]}
        lines = _format_setup_warning("isLoading", src, entry, "    ")
        text = "\n".join(lines)
        assert "loadingMixin.data" in text
        assert "useLoading" in text
        assert "unavailable in setup()" in text

    def test_component_source(self):
        entry = _make_entry("commentMixin")
        src = {"kind": "component", "detail": "TaskDetail.data", "sources": ["TaskDetail.data"]}
        lines = _format_setup_warning("entityId", src, entry, "    ")
        text = "\n".join(lines)
        assert "TaskDetail.data" in text
        assert "Replace with local ref" in text

    def test_ambiguous_source(self):
        entry = _make_entry("commentMixin")
        src = {"kind": "ambiguous", "detail": None, "sources": ["mixinA.data", "CompB.computed"]}
        lines = _format_setup_warning("status", src, entry, "    ")
        text = "\n".join(lines)
        assert "mixinA.data" in text
        assert "CompB.computed" in text
        assert "Ambiguous" in text

    def test_unknown_source(self):
        entry = _make_entry("commentMixin")
        src = {"kind": "unknown", "detail": None, "sources": []}
        lines = _format_setup_warning("mystery", src, entry, "    ")
        text = "\n".join(lines)
        assert "source not found" in text
        assert "props, inject" in text


class TestInjectSetupExternalDepWarnings:
    def test_injects_warnings_for_external_this_refs(self):
        lines = [
            "    onMounted(() => {",
            "      if (this.entityId) {",
            "        loadComments(this.entityId)",
            "      }",
            "    })",
        ]
        current = _make_entry("commentMixin", methods=["loadComments"])
        sibling = _make_entry("dataMixin", data=["entityId"])
        result = _inject_setup_external_dep_warnings(
            lines, current, [current, sibling], set(), "MyComp", "    ",
        )
        text = "\n".join(result)
        assert "entityId" in text
        assert "MIGRATION" in text
        assert "dataMixin.data" in text

    def test_no_warnings_when_no_external_refs(self):
        lines = [
            "    onMounted(() => {",
            "      doSomething()",
            "    })",
        ]
        entry = _make_entry("myMixin")
        result = _inject_setup_external_dep_warnings(
            lines, entry, [entry], set(), "Comp", "    ",
        )
        assert result == lines

    def test_deduplicates_warnings(self):
        lines = [
            "    this.ext + this.ext + this.ext",
        ]
        entry = _make_entry("myMixin")
        result = _inject_setup_external_dep_warnings(
            lines, entry, [entry], set(), "Comp", "    ",
        )
        warning_count = sum(1 for l in result if "MIGRATION" in l)
        # 1 MIGRATION header per warning, only 1 warning for 'ext'
        assert warning_count == 1

    def test_empty_lines_returns_empty(self):
        entry = _make_entry("myMixin")
        result = _inject_setup_external_dep_warnings(
            [], entry, [entry], set(), "Comp", "    ",
        )
        assert result == []
