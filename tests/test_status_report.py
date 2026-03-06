# tests/test_status_report.py
import pytest
from pathlib import Path
from vue3_migration.models import MigrationConfig
from vue3_migration.reporting.markdown import generate_status_report


@pytest.fixture
def dummy_project(tmp_path):
    """Minimal project: one component using authMixin, one composable useAuth."""
    (tmp_path / "src" / "mixins").mkdir(parents=True)
    (tmp_path / "src" / "composables").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)

    (tmp_path / "src" / "mixins" / "authMixin.js").write_text(
        "export default { data() { return { user: null } }, methods: { logout() {} } }"
    )
    (tmp_path / "src" / "composables" / "useAuth.js").write_text(
        "export function useAuth() { const user = ref(null); function logout() {} return { user, logout } }"
    )
    (tmp_path / "src" / "components" / "UserProfile.vue").write_text(
        "import authMixin from '../mixins/authMixin'\nexport default { mixins: [authMixin] }"
    )
    return tmp_path


def test_status_report_contains_summary_header(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "# Vue Migration Status Report" in report
    assert "ready" in report


def test_status_report_shows_component_count(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "1" in report  # 1 component with mixins


def test_status_report_lists_mixin_in_table(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "authMixin" in report


def test_status_report_shows_composable_found(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "found" in report


def test_status_report_lists_component_section(dummy_project):
    config = MigrationConfig(project_root=dummy_project)
    report = generate_status_report(dummy_project, config)
    assert "UserProfile.vue" in report
    assert "## Components" in report


def test_status_report_no_components_returns_empty_state(tmp_path):
    """Project with no .vue files -> summary shows 0 components."""
    config = MigrationConfig(project_root=tmp_path)
    report = generate_status_report(tmp_path, config)
    assert "0 components" in report or "0 blocked" in report
    assert "0" in report


def test_status_report_blocked_component(tmp_path):
    """Component using a mixin with no matching composable -> status is Blocked."""
    (tmp_path / "src" / "mixins").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "mixins" / "obscureMixin.js").write_text("export default {}")
    (tmp_path / "src" / "components" / "Foo.vue").write_text(
        "import obscureMixin from '../mixins/obscureMixin'\nexport default { mixins: [obscureMixin] }"
    )
    config = MigrationConfig(project_root=tmp_path)
    report = generate_status_report(tmp_path, config)
    assert "Blocked" in report
    assert "needs generation" in report
