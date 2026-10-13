"""CLI for the fs_tools package.

Provides the ``fs-tools`` command. With no subcommand it launches the GUI;
otherwise it dispatches to a database/template tool. Every subcommand is a
native Typer command: Typer parses and validates the arguments, then the
command body calls the tool's own ``run()`` coroutine.
"""

from __future__ import annotations

import asyncio
import multiprocessing
from pathlib import Path

import typer

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
        # Lazy import: fs_tools.gui pulls in PySide6, kept out of the CLI import
        # path so non-GUI subcommands stay light.
        from fs_tools.gui import run_gui

        run_gui()
        raise typer.Exit()


_ADD_ICON_EPILOG = """
Examples:
  # Add a normal Colonial rifle icon at 1080p (icon must be 32x32)
  fs-tools add-icon --database data/templates.h5 --icon rifle_32x32.png \\
    --code Rifle --faction c --category item \\
    --mod vanilla --resolution 1080

  # Add a crated Warden shippable icon at 2160p (icon must be 64x64)
  fs-tools add-icon --database data/templates.h5 --icon crate_64x64.png \\
    --code ShippableCrate --faction w --category shippable \\
    --crated --mod vanilla --resolution 2160

  # Add a neutral item at multiple resolutions (need separate sized icons)
  fs-tools add-icon --database data/templates.h5 --icon medkit_32x32.png \\
    --code Medkit --faction n --category item \\
    --mod vanilla --resolution 1080

  fs-tools add-icon --database data/templates.h5 --icon medkit_43x43.png \\
    --code Medkit --faction n --category item \\
    --mod vanilla --resolution 1440

Note: Icon dimensions must exactly match the target resolution requirements.
      Use: 664p=19px, 720p=21px, 1080p=32px, 1440p=43px, 2160p=64px
"""


@app.command("add-icon", epilog=_ADD_ICON_EPILOG)
def add_icon(
    icon: Path = typer.Option(..., "--icon", help="Path to icon image file."),
    code: str = typer.Option(..., "--code", help="Item code name (e.g., Rifle, LightTank)."),
    faction: str = typer.Option(
        ..., "--faction", help="Faction for the icon (e.g., 'c', 'w', 'n')."
    ),
    category: str = typer.Option(
        ..., "--category", help="Category for the icon (item, vehicle, or shippable)."
    ),
    mod: str = typer.Option(..., "--mod", help="Mod name (e.g., vanilla, modname)."),
    resolution: list[str] = typer.Option(
        ...,
        "--resolution",
        help="Target resolution (can be specified multiple times, e.g., --resolution 1080"
        " --resolution 2160).",
    ),
    database: Path | None = typer.Option(
        None, "--database", help="Path to existing template database (.h5 file)."
    ),
    crated: bool = typer.Option(False, "--crated", help="Mark this icon as a crated variant."),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Replace existing icon if one already exists with same metadata. Without this"
        " flag, attempting to add a duplicate will result in an error.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(
        False, "--quiet", help="Suppress all output except errors and warnings."
    ),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
) -> None:
    """Add a single icon to a template database."""
    from fs_tools.commands.add_icon.add_icon import run

    asyncio.run(
        run(
            icon=icon,
            code=code,
            faction=faction,
            category=category,
            mod=mod,
            resolution=resolution,
            database=database,
            crated=crated,
            replace=replace,
            verbose=verbose,
            quiet=quiet,
            log_file=log_file,
        )
    )


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
