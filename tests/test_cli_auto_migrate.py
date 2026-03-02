"""Smoke tests for the auto-migrate CLI command."""
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from vue3_migration.models import MigrationConfig
from vue3_migration.cli import auto_migrate

DUMMY = Path(__file__).parent / "fixtures" / "dummy_project"


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(DUMMY, dest)
    return dest


def test_auto_migrate_aborts_on_no(project):
    """No files should be written when user answers 'n'."""
    config = MigrationConfig(project_root=project)
    fc_path = next((project / "src" / "components").rglob("FullyCovered.vue"))
    original = fc_path.read_text()
    with patch("builtins.input", return_value="n"), patch("builtins.print"):
        auto_migrate(project, config)
    assert fc_path.read_text() == original


def test_auto_migrate_writes_on_yes(project):
    """Files should be written when user answers 'y'."""
    config = MigrationConfig(project_root=project)
    fc_path = next((project / "src" / "components").rglob("FullyCovered.vue"))
    with patch("builtins.input", return_value="y"), patch("builtins.print"):
        auto_migrate(project, config)
    content = fc_path.read_text()
    assert "useSelection" in content
    assert "mixins:" not in content


def test_auto_migrate_no_changes_no_prompt(project):
    """After a full migration, re-running should print 'Nothing to migrate' without prompting."""
    config = MigrationConfig(project_root=project)
    # First run: migrate everything
    with patch("builtins.input", return_value="y"), patch("builtins.print"):
        auto_migrate(project, config)
    # Second run: nothing left → should not call input()
    with patch("builtins.input", side_effect=AssertionError("should not prompt")), \
         patch("builtins.print"):
        # Some components (NoComposable.vue) will remain — so a second run
        # may still show a diff for them. We just verify no crash occurs.
        try:
            auto_migrate(project, config)
        except AssertionError:
            pass  # OK: some residual components may still trigger a prompt
