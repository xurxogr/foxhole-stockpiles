"""CLI for the fs_tools package.

Provides the ``fs-tools`` command. With no subcommand it launches the GUI;
``visualize`` and ``debug`` open a single tool window, ``import-display-names``
copies the names of the stockpile types from the game into the translations, and
``import-map-locations`` the named places of the map of each hex into the application. Catalog
and template database builds are done by the ``fs-assets`` command.
"""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

import foxhole_stockpiles.i18n
import foxhole_stockpiles.services.map_locations
from fs_tools.core.display_names_import import import_stockpile_names
from fs_tools.core.map_locations_import import import_map_locations
from fs_tools.gui import run_debug_viewer, run_gui, run_visualizer

_TRANSLATIONS_DIR = Path(foxhole_stockpiles.i18n.__file__).parent / "translations"
_LOCATION_TABLE = (
    Path(foxhole_stockpiles.services.map_locations.__file__).parent / "location_table.py"
)

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


@app.command("import-display-names")
def import_display_names(
    display_names: str = typer.Argument(..., help="Display names extracted by fs-assets"),
    translations: str = typer.Option(
        str(_TRANSLATIONS_DIR), "--translations", "-t", help="Directory of the translations"
    ),
) -> None:
    """Copy the names of the stockpile types from the game into the translations."""
    try:
        report = import_stockpile_names(
            display_names=Path(display_names), translations_dir=Path(translations)
        )
    except (OSError, ValueError, ValidationError) as e:
        typer.echo(f"Could not import the display names: {e}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Imported {report.imported} stockpile types into: {', '.join(report.languages)}")
    if report.not_in_enum:
        typer.echo(f"Not in StockpileType: {', '.join(report.not_in_enum)}")


@app.command("import-map-locations")
def import_map_locations_command(
    map_locations: str = typer.Argument(..., help="Map locations extracted by fs-assets"),
    output: str = typer.Option(
        str(_LOCATION_TABLE), "--output", "-o", help="Module of the places to write"
    ),
) -> None:
    """Copy the named places of the map of each hex from the game into the application."""
    try:
        report = import_map_locations(map_locations=Path(map_locations), output=Path(output))
    except (OSError, ValueError, ValidationError) as e:
        typer.echo(f"Could not import the map locations: {e}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Imported {report.locations} places of {report.hexes} hexes into {output}")
    if report.not_in_enum:
        typer.echo(f"Not in Hex: {', '.join(report.not_in_enum)}")


def main() -> None:
    """Entry point for the fs-tools CLI."""
    app()


if __name__ == "__main__":
    main()
