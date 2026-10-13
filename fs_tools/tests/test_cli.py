"""Tests for the ``fs-tools`` CLI shell (``fs_tools.cli``).

Every tool subcommand is a native Typer command that parses/validates its own
arguments and calls the tool module's ``run()`` coroutine via ``asyncio.run``.
Each tool's ``run()`` is patched so these tests cover the CLI wiring (option
parsing and forwarding) without executing the real pipelines.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from fs_tools import cli

runner = CliRunner()


def test_no_subcommand_launches_gui() -> None:
    """Invoking with no subcommand launches the tools GUI."""
    with patch("fs_tools.gui.run_gui") as run_gui:
        result = runner.invoke(cli.app, [])
    run_gui.assert_called_once()
    assert result.exit_code == 0


def test_add_icon_forwards_options() -> None:
    """``add-icon`` forwards parsed options to ``add_icon.run``."""
    with patch("fs_tools.commands.add_icon.add_icon.run", new_callable=AsyncMock) as run:
        result = runner.invoke(
            cli.app,
            [
                "add-icon",
                "--database",
                "db.h5",
                "--icon",
                "icon.png",
                "--code",
                "Rifle",
                "--faction",
                "c",
                "--category",
                "item",
                "--mod",
                "vanilla",
                "--resolution",
                "1080",
                "--crated",
                "--replace",
            ],
        )
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        icon=Path("icon.png"),
        code="Rifle",
        faction="c",
        category="item",
        mod="vanilla",
        resolution=["1080"],
        database=Path("db.h5"),
        crated=True,
        replace=True,
        verbose=False,
        quiet=False,
        log_file=None,
    )


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
