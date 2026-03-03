# tests/test_cli_menu.py
import pytest
from unittest.mock import patch, MagicMock
from vue3_migration.cli import main


def test_menu_shows_four_options(capsys):
    with patch("builtins.input", return_value="q"):
        main([])
    out = capsys.readouterr().out
    assert "Full project" in out
    assert "Pick a component" in out
    assert "Pick a mixin" in out
    assert "Project status" in out


def test_main_dispatches_all():
    with patch("vue3_migration.cli.full_project_migration") as mock:
        main(["all"])
    mock.assert_called_once()


def test_main_dispatches_component():
    with patch("vue3_migration.cli.component_migration") as mock:
        main(["component", "src/components/Foo.vue"])
    mock.assert_called_once()


def test_main_dispatches_mixin():
    with patch("vue3_migration.cli.mixin_migration") as mock:
        main(["mixin", "authMixin"])
    mock.assert_called_once()


def test_main_dispatches_status():
    with patch("vue3_migration.cli.project_status") as mock:
        main(["status"])
    mock.assert_called_once()


def test_main_unknown_command_prints_message(capsys):
    main(["foobar"])
    out = capsys.readouterr().out
    assert "Unknown command" in out


def test_main_component_missing_path_prints_usage(capsys):
    main(["component"])
    out = capsys.readouterr().out
    assert "Usage" in out


def test_main_mixin_missing_name_prints_usage(capsys):
    main(["mixin"])
    out = capsys.readouterr().out
    assert "Usage" in out


def test_main_help_flags_print_usage(capsys):
    for flag in ["--help", "-h", "help"]:
        main([flag])
        out = capsys.readouterr().out
        assert "Usage" in out, f"Expected 'Usage' in output for {flag}"


def test_menu_quit_calls_no_stubs():
    with patch("builtins.input", return_value="q"), \
         patch("vue3_migration.cli.full_project_migration") as m1, \
         patch("vue3_migration.cli.pick_component_migration") as m2, \
         patch("vue3_migration.cli.pick_mixin_migration") as m3, \
         patch("vue3_migration.cli.project_status") as m4:
        main([])
    m1.assert_not_called()
    m2.assert_not_called()
    m3.assert_not_called()
    m4.assert_not_called()
