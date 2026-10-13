"""CLI for the fs_tools package.

Provides the ``fs-tools`` command. With no subcommand it launches the GUI;
``visualize`` and ``debug`` open a single tool window. Catalog and template
database builds are done by the ``fs-assets`` command.
"""

from __future__ import annotations

from pathlib import Path

import typer

from fs_tools.gui import run_debug_viewer, run_gui, run_visualizer

app = typer.Typer(
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
    help="Foxhole Stockpiles database and template tools.",
)


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Launch the tools GUI when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        run_gui()
        raise typer.Exit()


@app.command()
def visualize(
    database: str | None = typer.Option(None, "--database", "-d", help="Template database to open"),
) -> None:
    """Open the database visualizer GUI."""
    run_visualizer(Path(database) if database else None)


@app.command()
def debug(
    image: str = typer.Argument(..., help="Screenshot to inspect"),
    database: str = typer.Option(..., "--database", "-d", help="Template database to use"),
) -> None:
    """Open the debug image viewer for a screenshot."""
    run_debug_viewer(Path(image), Path(database))


def main() -> None:
    """Entry point for the fs-tools CLI."""
    app()


if __name__ == "__main__":
    main()
