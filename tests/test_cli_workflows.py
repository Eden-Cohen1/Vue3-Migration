# tests/test_cli_workflows.py
"""Tests for the new workflow functions in cli.py."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from vue3_migration.cli import (
    full_project_migration,
    component_migration,
    mixin_migration,
    pick_component_migration,
    pick_mixin_migration,
    project_status,
)
from vue3_migration.models import MigrationConfig, MigrationPlan, FileChange


def _empty_plan():
    return MigrationPlan(composable_changes=[], component_changes=[])


def _plan_with_change(tmp_path):
    change = FileChange(
        file_path=tmp_path / "Foo.vue",
        original_content="old",
        new_content="new",
        changes=[],
    )
    return MigrationPlan(composable_changes=[], component_changes=[change])


# --- full_project_migration ---

def test_full_project_nothing_to_migrate(capsys):
    config = MigrationConfig()
    with patch("vue3_migration.workflows.auto_migrate_workflow.run", return_value=_empty_plan()):
        full_project_migration(config)
    out = capsys.readouterr().out
    assert "Nothing to migrate" in out


def test_full_project_aborted_on_n(tmp_path, capsys):
    config = MigrationConfig(project_root=tmp_path)
    plan = _plan_with_change(tmp_path)
    with patch("vue3_migration.workflows.auto_migrate_workflow.run", return_value=plan), \
         patch("vue3_migration.reporting.diff.format_change_list", return_value=""), \
         patch("builtins.input", return_value="n"):
        full_project_migration(config)
    out = capsys.readouterr().out
    assert "Aborted" in out
    assert not (tmp_path / "Foo.vue").exists()


# --- component_migration ---

def test_component_migration_not_found_prints_message(capsys):
    config = MigrationConfig()
    component_migration("nonexistent/path/Foo.vue", config)
    out = capsys.readouterr().out
    assert "not found" in out.lower()


# --- mixin_migration ---

def test_mixin_migration_strips_extension():
    config = MigrationConfig()
    with patch("vue3_migration.cli._run_mixin_migration") as mock:
        mixin_migration("authMixin.js", config)
    mock.assert_called_once_with("authMixin", config)


def test_mixin_migration_nothing_to_migrate(capsys):
    config = MigrationConfig()
    with patch("vue3_migration.workflows.auto_migrate_workflow.run_scoped", return_value=_empty_plan()):
        mixin_migration("authMixin", config)
    out = capsys.readouterr().out
    assert "Nothing to migrate" in out


# --- project_status ---

def test_project_status_creates_report_file(tmp_path):
    config = MigrationConfig(project_root=tmp_path)
    with patch("vue3_migration.reporting.markdown.generate_status_report", return_value="# Report\n## Summary\n"):
        project_status(config)
    report_files = list(tmp_path.glob("migration-status-*.md"))
    assert len(report_files) == 1
    assert "# Report" in report_files[0].read_text()


def test_project_status_prints_summary(tmp_path, capsys):
    config = MigrationConfig(project_root=tmp_path)
    with patch("vue3_migration.reporting.markdown.generate_status_report", return_value="# Report\n## Summary\n- Ready: 3\n"):
        project_status(config)
    out = capsys.readouterr().out
    assert "Summary" in out
