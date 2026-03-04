# tests/test_diff_reporting.py
from pathlib import Path
import pytest
from vue3_migration.models import (
    FileChange, MigrationPlan, MigrationWarning, MixinEntry, MixinMembers,
)
from vue3_migration.reporting.diff import format_change_list, write_diff_report


def _change(path, original, new):
    return FileChange(file_path=Path(path), original_content=original, new_content=new, changes=[])


def test_detects_added_ref():
    original = "export function useTable() {\n  return {}\n}"
    new = "export function useTable() {\n  const tableData = ref([])\n  return { tableData }\n}"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", original, new)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useTable.js" in out
    assert "tableData" in out
    assert "refs" in out


def test_detects_added_function():
    original = "export function useTable() {\n  return {}\n}"
    new = "export function useTable() {\n  function fetchRows() {}\n  return { fetchRows }\n}"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", original, new)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "fetchRows" in out
    assert "function" in out


def test_detects_new_composable_file():
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useAuth.js", "", "export function useAuth() { return {} }")],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useAuth.js" in out
    assert "new file" in out


def test_detects_removed_mixin_import():
    original = "import authMixin from '../mixins/authMixin'\nexport default { mixins: [authMixin] }"
    new = "import { useAuth } from '../composables/useAuth'\nexport default { setup() { const { user } = useAuth(); return { user } } }"
    plan = MigrationPlan(
        component_changes=[_change("src/components/UserProfile.vue", original, new)],
        composable_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "UserProfile.vue" in out
    assert "authMixin" in out


def test_detects_added_composable_import():
    original = "import authMixin from '../mixins/authMixin'\nexport default { mixins: [authMixin] }"
    new = "import { useAuth } from '../composables/useAuth'\nexport default { setup() { return {} } }"
    plan = MigrationPlan(
        component_changes=[_change("src/components/UserProfile.vue", original, new)],
        composable_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useAuth" in out


def test_skips_unchanged_files():
    content = "export function useTable() { return {} }"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", content, content)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "useTable.js" not in out


def test_write_diff_report_creates_md_file(tmp_path):
    original = "export function useTable() {\n  return {}\n}"
    new = "export function useTable() {\n  const data = ref([])\n  return { data }\n}"
    change = _change(str(tmp_path / "useTable.js"), original, new)
    plan = MigrationPlan(composable_changes=[change], component_changes=[])

    report_path = write_diff_report(plan, tmp_path)

    assert report_path.exists()
    content = report_path.read_text()
    assert "useTable.js" in content
    assert "```diff" in content


def test_write_diff_report_new_file_uses_code_block(tmp_path):
    change = _change(str(tmp_path / "useAuth.js"), "", "export function useAuth() { return {} }")
    plan = MigrationPlan(composable_changes=[change], component_changes=[])

    report_path = write_diff_report(plan, tmp_path)

    content = report_path.read_text()
    assert "New file" in content
    assert "```javascript" in content


def test_no_false_positive_for_existing_ref():
    """Refs that already existed in the composable should not appear as new."""
    original = "export function useTable() {\n  const tableData = ref([])\n  return { tableData }\n}"
    new = "export function useTable() {\n  const tableData = ref([])\n  const loading = ref(false)\n  return { tableData, loading }\n}"
    plan = MigrationPlan(
        composable_changes=[_change("src/composables/useTable.js", original, new)],
        component_changes=[],
    )
    out = format_change_list(plan, Path("."))
    assert "loading" in out
    assert "tableData" not in out  # already existed, should not appear


def test_write_diff_report_includes_warning_summary(tmp_path):
    """When entries_by_component has warnings, the summary appears before diffs."""
    change = _change(str(tmp_path / "useAuth.js"), "", "export function useAuth() { return {} }")
    w = MigrationWarning("authMixin", "this.$router", "not available", "Use useRouter()", None, "warning")
    entry = MixinEntry(
        local_name="authMixin",
        mixin_path="fake/authMixin.js",
        mixin_stem="authMixin",
        members=MixinMembers(),
    )
    entry.warnings = [w]
    plan = MigrationPlan(
        composable_changes=[change],
        component_changes=[],
        entries_by_component=[(Path("fake/Comp.vue"), [entry])],
    )

    report_path = write_diff_report(plan, tmp_path)
    content = report_path.read_text(encoding="utf-8")

    assert "## Migration Summary" in content
    assert "- [ ]" in content
    assert "Use useRouter()" in content
    # Summary should appear before the diff
    summary_pos = content.index("## Migration Summary")
    diff_pos = content.index("## `")
    assert summary_pos < diff_pos
