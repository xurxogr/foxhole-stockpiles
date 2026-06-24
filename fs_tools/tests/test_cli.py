"""Tests for the ``fs-tools`` CLI shell (``fs_tools.cli``).

The CLI is a thin Typer shell that either launches a GUI or delegates to a
tool's ``argparse`` ``main()``. GUI launchers and delegation are patched so the
tests cover the dispatch wiring without opening windows or running tools.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from fs_tools import cli

runner = CliRunner()

PASSTHROUGH_COMMANDS = [
    "build-catalog",
    "build-db",
    "generate-templates",
    "extract-assets",
    "add-icon",
    "add-mod",
]


def test_no_subcommand_launches_gui() -> None:
    """Invoking with no subcommand launches the tools GUI."""
    with patch("fs_tools.gui.run_gui") as run_gui:
        result = runner.invoke(cli.app, [])
    run_gui.assert_called_once()
    assert result.exit_code == 0


@pytest.mark.parametrize("command", PASSTHROUGH_COMMANDS)
def test_passthrough_command_delegates(command: str) -> None:
    """Each pass-through subcommand forwards its raw args to ``_delegate``."""
    with patch.object(cli, "_delegate") as delegate:
        result = runner.invoke(cli.app, [command, "--foo", "bar"])
    assert result.exit_code == 0
    delegate.assert_called_once_with(command, ["--foo", "bar"])


def test_delegate_runs_module_main_and_restores_argv() -> None:
    """``_delegate`` runs the module's async ``main`` and restores ``sys.argv``."""
    ran = {"called": False}

    async def fake_main() -> None:
        ran["called"] = True

    module = MagicMock()
    module.main = fake_main
    original_argv = sys.argv

    with patch("importlib.import_module", return_value=module) as import_module:
        cli._delegate("build-db", ["--x", "1"])

    import_module.assert_called_once_with(cli._COMMAND_MODULES["build-db"])
    assert ran["called"] is True
    assert sys.argv is original_argv


def test_visualize_opens_visualizer() -> None:
    """``visualize`` opens the database visualizer GUI."""
    with patch("fs_tools.gui.run_visualizer") as run_visualizer:
        result = runner.invoke(cli.app, ["visualize", "--database", "db.h5"])
    assert result.exit_code == 0
    run_visualizer.assert_called_once()


def test_visualize_without_database() -> None:
    """``visualize`` with no database passes None."""
    with patch("fs_tools.gui.run_visualizer") as run_visualizer:
        result = runner.invoke(cli.app, ["visualize"])
    assert result.exit_code == 0
    run_visualizer.assert_called_once_with(None)


def test_debug_opens_viewer() -> None:
    """``debug`` opens the debug image viewer."""
    with patch("fs_tools.gui.run_debug_viewer") as run_debug_viewer:
        result = runner.invoke(cli.app, ["debug", "shot.png", "--database", "db.h5"])
    assert result.exit_code == 0
    run_debug_viewer.assert_called_once()


def test_main_runs_app() -> None:
    """``main`` initializes multiprocessing support and runs the Typer app."""
    with (
        patch.object(cli, "app") as app,
        patch("fs_tools.cli.multiprocessing.freeze_support") as freeze_support,
    ):
        cli.main()
    freeze_support.assert_called_once()
    app.assert_called_once()
