"""Smoke tests for scoped auto-migrate CLI subcommands.

Tests:
  auto-migrate component <Component.vue>  — scoped to a single component
  auto-migrate mixin <mixin.js>           — scoped to all components using that mixin
"""
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from vue3_migration.models import MigrationConfig
from vue3_migration.cli import auto_migrate_scoped

DUMMY = Path(__file__).parent / "fixtures" / "dummy_project"


@pytest.fixture
def project(tmp_path):
    dest = tmp_path / "proj"
    shutil.copytree(DUMMY, dest)
    return dest


# ── component scope ──────────────────────────────────────────────────────────

def test_component_scope_writes_only_target(project):
    """Only the targeted component should be changed."""
    config = MigrationConfig(project_root=project)
    fc_path = next((project / "src" / "components").rglob("FullyCovered.vue"))
    multi_path = next((project / "src" / "components").rglob("MultiMixin.vue"))
    multi_original = multi_path.read_text()

    with patch("builtins.input", return_value="y"), patch("builtins.print"):
        auto_migrate_scoped(str(fc_path), "component", config)

    content = fc_path.read_text()
    assert "useSelection" in content
    assert "mixins:" not in content
    # Other component unchanged
    assert multi_path.read_text() == multi_original


def test_component_scope_aborts_on_no(project):
    """No files written when user answers 'n'."""
    config = MigrationConfig(project_root=project)
    fc_path = next((project / "src" / "components").rglob("FullyCovered.vue"))
    original = fc_path.read_text()

    with patch("builtins.input", return_value="n"), patch("builtins.print"):
        auto_migrate_scoped(str(fc_path), "component", config)

    assert fc_path.read_text() == original


def test_component_scope_file_not_found_returns_gracefully(project, capsys):
    """Non-existent component path should print an error and not raise."""
    config = MigrationConfig(project_root=project)
    with patch("builtins.print"):
        auto_migrate_scoped("/nonexistent/Ghost.vue", "component", config)
    # Should not raise, no crash


def test_component_scope_no_mixins_exits_early(project):
    """A component with no mixins should exit without prompting."""
    config = MigrationConfig(project_root=project)
    # Create a minimal component with no mixins
    plain = project / "src" / "components" / "Plain.vue"
    plain.write_text("<template><div/></template>\n<script>\nexport default { name: 'Plain' }\n</script>\n")

    with patch("builtins.input", side_effect=AssertionError("should not prompt")), \
         patch("builtins.print"):
        auto_migrate_scoped(str(plain), "component", config)  # should not raise


# ── mixin scope ───────────────────────────────────────────────────────────────

def test_mixin_scope_writes_all_using_components(project):
    """All components that use selectionMixin should be migrated."""
    config = MigrationConfig(project_root=project)
    mixin_path = next((project / "src" / "mixins").rglob("selectionMixin.js"))

    with patch("builtins.input", return_value="y"), patch("builtins.print"):
        auto_migrate_scoped(str(mixin_path), "mixin", config)

    fc = next((project / "src" / "components").rglob("FullyCovered.vue"))
    assert "useSelection" in fc.read_text()


def test_mixin_scope_aborts_on_no(project):
    """No files written when user answers 'n'."""
    config = MigrationConfig(project_root=project)
    mixin_path = next((project / "src" / "mixins").rglob("selectionMixin.js"))
    fc_path = next((project / "src" / "components").rglob("FullyCovered.vue"))
    original = fc_path.read_text()

    with patch("builtins.input", return_value="n"), patch("builtins.print"):
        auto_migrate_scoped(str(mixin_path), "mixin", config)

    assert fc_path.read_text() == original


def test_mixin_scope_does_not_touch_unrelated_components(project):
    """Components that don't use the targeted mixin are unchanged."""
    config = MigrationConfig(project_root=project)
    mixin_path = next((project / "src" / "mixins").rglob("selectionMixin.js"))

    # NoComposable uses authMixin, not selectionMixin
    no_comp = next((project / "src" / "components").rglob("NoComposable.vue"))
    no_comp_original = no_comp.read_text()

    with patch("builtins.input", return_value="y"), patch("builtins.print"):
        auto_migrate_scoped(str(mixin_path), "mixin", config)

    assert no_comp.read_text() == no_comp_original


def test_mixin_scope_file_not_found_returns_gracefully(project):
    """Non-existent mixin path should print an error and not raise."""
    config = MigrationConfig(project_root=project)
    with patch("builtins.print"):
        auto_migrate_scoped("/nonexistent/ghostMixin.js", "mixin", config)
    # Should not raise
