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


def test_build_catalog_forwards_options() -> None:
    """``build-catalog`` forwards parsed options to ``catalog_builder.run``."""
    with patch(
        "fs_tools.commands.catalog_builder.catalog_builder.run", new_callable=AsyncMock
    ) as run:
        result = runner.invoke(
            cli.app,
            [
                "build-catalog",
                "--pak",
                "game.pak",
                "--extractor",
                "repak.exe",
                "--converter",
                "conv.exe",
                "--output",
                "catalog.json",
                "--keep-temp",
                "--force-extract",
                "--workers",
                "8",
                "--log-file",
                "log.txt",
                "--verbose",
                "--extract-dir",
                "extracted",
            ],
        )
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        pak=Path("game.pak"),
        extractor=Path("repak.exe"),
        converter=Path("conv.exe"),
        output=Path("catalog.json"),
        keep_temp=True,
        force_extract=True,
        workers=8,
        log_file=Path("log.txt"),
        verbose=True,
        quiet=False,
        extract_dir=Path("extracted"),
    )


def test_build_db_forwards_options() -> None:
    """``build-db`` forwards parsed options to ``database_builder.run``."""
    with patch(
        "fs_tools.commands.database_builder.database_builder.run", new_callable=AsyncMock
    ) as run:
        result = runner.invoke(
            cli.app,
            [
                "build-db",
                "--templates",
                "templates/",
                "--catalog",
                "catalog.json",
                "--database",
                "db.h5",
                "--use-scaling",
                "--resolution",
                "1080",
                "--resolution",
                "2160",
            ],
        )
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        templates=Path("templates/"),
        catalog=Path("catalog.json"),
        database=Path("db.h5"),
        use_scaling=True,
        verbose=False,
        quiet=False,
        log_file=None,
        resolution=["1080", "2160"],
    )


def test_generate_templates_forwards_options() -> None:
    """``generate-templates`` forwards parsed options to ``generate_templates.run``."""
    with patch(
        "fs_tools.commands.generate_templates.generate_templates.run", new_callable=AsyncMock
    ) as run:
        result = runner.invoke(
            cli.app,
            [
                "generate-templates",
                "--assets",
                "assets/",
                "--templates",
                "templates/",
                "--catalog",
                "catalog.json",
                "--filter",
                "Rifle",
                "--quiet",
            ],
        )
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        assets=Path("assets/"),
        templates=Path("templates/"),
        catalog=Path("catalog.json"),
        filter="Rifle",
        verbose=False,
        quiet=True,
        log_file=None,
    )


def test_extract_assets_forwards_options() -> None:
    """``extract-assets`` forwards parsed options to ``uasset_extractor.run``."""
    with patch(
        "fs_tools.commands.uasset_extractor.uasset_extractor.run", new_callable=AsyncMock
    ) as run:
        result = runner.invoke(
            cli.app,
            [
                "extract-assets",
                "--pak",
                "a.pak",
                "--pak",
                "b.pak",
                "--catalog",
                "catalog.json",
                "--extractor-tool",
                "repak.exe",
                "--converter-tool",
                "conv.exe",
                "--output",
                "out/",
                "--workers",
                "2",
                "--filter-files",
                "foo.uasset",
                "--filter-pattern",
                "Subicons/",
            ],
        )
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        pak=["a.pak", "b.pak"],
        catalog="catalog.json",
        extractor_tool="repak.exe",
        converter_tool="conv.exe",
        output="out/",
        workers=2,
        filter_files=["foo.uasset"],
        filter_pattern=["Subicons/"],
        log_file=None,
        verbose=False,
        quiet=False,
    )


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


def test_add_mod_forwards_options() -> None:
    """``add-mod`` forwards parsed options to ``add_mod.run``."""
    with patch("fs_tools.commands.add_mod.add_mod.run", new_callable=AsyncMock) as run:
        result = runner.invoke(
            cli.app,
            [
                "add-mod",
                "--name",
                "My Mod",
                "--pak",
                "mod.pak",
                "--vanilla",
                "vanilla.pak",
                "--overwrite",
                "--resolution",
                "1080",
                "--extract-only",
                "--extract-dir",
                "extracted/",
                "--workers",
                "4",
            ],
        )
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(
        mod_name="My Mod",
        pak_files=[Path("mod.pak")],
        vanilla_pak=Path("vanilla.pak"),
        catalog=None,
        database=None,
        extractor=None,
        converter=None,
        overwrite=True,
        resolutions=["1080"],
        extract_dir=Path("extracted/"),
        extract_only=True,
        workers=4,
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
