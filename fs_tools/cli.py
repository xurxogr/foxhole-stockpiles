"""CLI for the fs_tools package.

Provides the ``fs-tools`` command. With no subcommand it launches the GUI;
otherwise it dispatches to a database/template tool.

Each tool subcommand is a thin pass-through that delegates to the tool's
existing ``argparse``-based ``main()`` coroutine. Typer is used only as the
entry shell, so the underlying tools keep their established arguments and
``--help`` output until the CLI is unified in a later phase.
"""

from __future__ import annotations

import asyncio
import importlib
import multiprocessing
import sys
from pathlib import Path

import typer

app = typer.Typer(
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
    help="Foxhole Stockpiles database and template tools.",
)

# Subcommand name -> module exposing an async ``main()`` entry point.
_COMMAND_MODULES: dict[str, str] = {
    "build-catalog": "fs_tools.commands.catalog_builder.catalog_builder",
    "build-db": "fs_tools.commands.database_builder.database_builder",
    "generate-templates": "fs_tools.commands.generate_templates.generate_templates",
    "extract-assets": "fs_tools.commands.uasset_extractor.uasset_extractor",
    "add-icon": "fs_tools.commands.add_icon.add_icon",
    "add-mod": "fs_tools.commands.add_mod.add_mod",
}

# Hand all arguments (including --help) to the wrapped argparse parser.
_PASSTHROUGH = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
    "help_option_names": [],
}


def _delegate(command: str, args: list[str]) -> None:
    """Run a wrapped tool's ``main()`` coroutine with the given arguments.

    Args:
        command (str): The fs-tools subcommand name.
        args (list[str]): Raw arguments to forward to the tool.
    """
    module = importlib.import_module(_COMMAND_MODULES[command])
    original_argv = sys.argv
    sys.argv = [f"fs-tools {command}", *args]
    try:
        asyncio.run(module.main())
    finally:
        sys.argv = original_argv


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Launch the tools GUI when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        # Lazy import: fs_tools.gui pulls in PySide6, kept out of the CLI import
        # path so non-GUI subcommands stay light.
        from fs_tools.gui import run_gui

        run_gui()
        raise typer.Exit()


@app.command("build-catalog", context_settings=_PASSTHROUGH)
def build_catalog(ctx: typer.Context) -> None:
    """Build catalog.json from PAK files."""
    _delegate("build-catalog", ctx.args)


@app.command("build-db", context_settings=_PASSTHROUGH)
def build_db(ctx: typer.Context) -> None:
    """Build a template database (.h5) from PAK files."""
    _delegate("build-db", ctx.args)


@app.command("generate-templates", context_settings=_PASSTHROUGH)
def generate_templates(ctx: typer.Context) -> None:
    """Generate resolution-specific templates."""
    _delegate("generate-templates", ctx.args)


@app.command("extract-assets", context_settings=_PASSTHROUGH)
def extract_assets(ctx: typer.Context) -> None:
    """Extract assets from Foxhole PAK files."""
    _delegate("extract-assets", ctx.args)


@app.command("add-icon", context_settings=_PASSTHROUGH)
def add_icon(ctx: typer.Context) -> None:
    """Add a single icon to a template database."""
    _delegate("add-icon", ctx.args)


@app.command("add-mod", context_settings=_PASSTHROUGH)
def add_mod(ctx: typer.Context) -> None:
    """Add mod content to a template database (full pipeline)."""
    _delegate("add-mod", ctx.args)


@app.command()
def visualize(
    database: str | None = typer.Option(None, "--database", "-d", help="Template database to open"),
) -> None:
    """Open the database visualizer GUI."""
    # Lazy import: fs_tools.gui pulls in PySide6 (see main_callback).
    from fs_tools.gui import run_visualizer

    run_visualizer(Path(database) if database else None)


@app.command()
def debug(
    image: str = typer.Argument(..., help="Screenshot to inspect"),
    database: str = typer.Option(..., "--database", "-d", help="Template database to use"),
) -> None:
    """Open the debug image viewer for a screenshot."""
    # Lazy import: fs_tools.gui pulls in PySide6 (see main_callback).
    from fs_tools.gui import run_debug_viewer

    run_debug_viewer(Path(image), Path(database))


def main() -> None:
    """Entry point for the fs-tools CLI."""
    multiprocessing.freeze_support()
    app()


if __name__ == "__main__":
    main()
