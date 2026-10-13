"""Tests for the ``fs-tools`` CLI shell (``fs_tools.cli``).

Every subcommand opens a GUI window; the window launchers are patched so these
tests cover the CLI wiring (option parsing and forwarding) without opening any.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from fs_tools import cli

runner = CliRunner()


def test_no_subcommand_launches_gui() -> None:
    """Invoking with no subcommand launches the tools GUI."""
    with patch("fs_tools.cli.run_gui") as run_gui:
        result = runner.invoke(cli.app, [])
    run_gui.assert_called_once()
    assert result.exit_code == 0


def test_visualize_opens_visualizer() -> None:
    """``visualize`` opens the database visualizer GUI."""
    with patch("fs_tools.cli.run_visualizer") as run_visualizer:
        result = runner.invoke(cli.app, ["visualize", "--database", "db.h5"])
    assert result.exit_code == 0
    run_visualizer.assert_called_once()


def test_visualize_without_database() -> None:
    """``visualize`` with no database passes None."""
    with patch("fs_tools.cli.run_visualizer") as run_visualizer:
        result = runner.invoke(cli.app, ["visualize"])
    assert result.exit_code == 0
    run_visualizer.assert_called_once_with(None)


def test_debug_opens_viewer() -> None:
    """``debug`` opens the debug image viewer."""
    with patch("fs_tools.cli.run_debug_viewer") as run_debug_viewer:
        result = runner.invoke(cli.app, ["debug", "shot.png", "--database", "db.h5"])
    assert result.exit_code == 0
    run_debug_viewer.assert_called_once()


def test_main_runs_app() -> None:
    """``main`` runs the Typer app."""
    with patch.object(cli, "app") as app:
        cli.main()
    app.assert_called_once()
