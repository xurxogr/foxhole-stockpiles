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


_CATALOG_BUILDER_DEFAULT_PAK = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Foxhole\War\Content\Paks"
    r"\War-WindowsNoEditor.pak"
)
_CATALOG_BUILDER_DEFAULT_EXTRACTOR = r"C:\repak\repak.exe"
_CATALOG_BUILDER_DEFAULT_CONVERTER = r"C:\UAssetGUI\UAssetGUI.exe"
_CATALOG_BUILDER_DEFAULT_OUTPUT = "catalog.json"


@app.command("build-catalog")
def build_catalog(
    pak: Path = typer.Option(
        Path(_CATALOG_BUILDER_DEFAULT_PAK), "--pak", help="Path to War-WindowsNoEditor.pak file."
    ),
    extractor: Path = typer.Option(
        Path(_CATALOG_BUILDER_DEFAULT_EXTRACTOR),
        "--extractor",
        help="Path to repak.exe extraction tool.",
    ),
    converter: Path = typer.Option(
        Path(_CATALOG_BUILDER_DEFAULT_CONVERTER),
        "--converter",
        help="Path to UAssetGUI.exe conversion tool.",
    ),
    output: Path = typer.Option(
        Path(_CATALOG_BUILDER_DEFAULT_OUTPUT), "--output", help="Output path for catalog JSON."
    ),
    keep_temp: bool = typer.Option(
        False, "--keep-temp", help="Keep temporary extraction directory."
    ),
    force_extract: bool = typer.Option(
        False, "--force-extract", help="Force re-extraction from PAK even if JSON files exist."
    ),
    workers: int = typer.Option(4, "--workers", help="Number of parallel conversions."),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress all output except errors."),
    extract_dir: Path | None = typer.Option(
        None,
        "--extract-dir",
        help="Use existing extraction directory instead of extracting from PAK (e.g., war/).",
    ),
) -> None:
    """Build catalog.json from PAK files."""
    from fs_tools.commands.catalog_builder.catalog_builder import run

    asyncio.run(
        run(
            pak=pak,
            extractor=extractor,
            converter=converter,
            output=output,
            keep_temp=keep_temp,
            force_extract=force_extract,
            workers=workers,
            log_file=log_file,
            verbose=verbose,
            quiet=quiet,
            extract_dir=extract_dir,
        )
    )


@app.command("build-db")
def build_db(
    templates: Path = typer.Option(..., "--templates", help="Path to extracted templates."),
    catalog: Path | None = typer.Option(
        None,
        "--catalog",
        help="Path to catalog.json (default: from database_builder.catalog_file setting).",
    ),
    database: Path | None = typer.Option(
        None,
        "--database",
        help="Output database path (default: from scanner.database_path setting).",
    ),
    use_scaling: bool = typer.Option(
        False,
        "--use-scaling",
        help="Scale from largest available size when exact size not found (better quality).",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress all output except errors and warnings. Only errors will be printed"
        " to console.",
    ),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
    resolution: list[str] | None = typer.Option(
        None,
        "--resolution",
        help="Resolution to generate (can be specified multiple times, e.g., --resolution"
        " 1024 --resolution 2160). If not specified, uses database_builder.target_resolutions"
        " setting or all supported resolutions if not configured.",
    ),
) -> None:
    """Build a template database (.h5) from PAK files."""
    from fs_tools.commands.database_builder.database_builder import run

    asyncio.run(
        run(
            templates=templates,
            catalog=catalog,
            database=database,
            use_scaling=use_scaling,
            verbose=verbose,
            quiet=quiet,
            log_file=log_file,
            resolution=resolution,
        )
    )


@app.command("generate-templates")
def generate_templates(
    assets: Path = typer.Option(
        ...,
        "--assets",
        help="Path to the folder containing extracted assets (with mod subfolders).",
    ),
    templates: Path = typer.Option(
        ..., "--templates", help="Path where generated templates will be saved."
    ),
    catalog: Path | None = typer.Option(
        None,
        "--catalog",
        help="Path to catalog.json file (default: from database_builder.catalog_file setting).",
    ),
    filter: str | None = typer.Option(
        None, "--filter", help="Filter items by CodeName containing this string (case-insensitive)."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress all output except errors and warnings. Only errors will be printed"
        " to console.",
    ),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
) -> None:
    """Generate resolution-specific templates."""
    from fs_tools.commands.generate_templates.generate_templates import run

    asyncio.run(
        run(
            assets=assets,
            templates=templates,
            catalog=catalog,
            filter=filter,
            verbose=verbose,
            quiet=quiet,
            log_file=log_file,
        )
    )


@app.command("extract-assets")
def extract_assets(
    pak: list[str] | None = typer.Option(
        None,
        "--pak",
        help="Path to PAK file(s). Can be specified multiple times for mod support.",
    ),
    catalog: str | None = typer.Option(
        None,
        "--catalog",
        help="Path to catalog.json file (default: from database_builder.catalog_file setting).",
    ),
    extractor_tool: str | None = typer.Option(
        None,
        "--extractor-tool",
        help="Path to repak.exe (default: from database_builder.extractor_tool setting).",
    ),
    converter_tool: str | None = typer.Option(
        None,
        "--converter-tool",
        help="Path to umodel.exe (default: from database_builder.converter_tool setting).",
    ),
    output: str = typer.Option("output", "--output", help="Output directory for converted files."),
    workers: int | None = typer.Option(
        None, "--workers", help="Number of parallel operations (default: cpu count)."
    ),
    filter_files: list[str] | None = typer.Option(
        None,
        "--filter-files",
        help="Extract only these specific file paths. Can be specified multiple times."
        " Example: --filter-files 'War/Content/Icons/Icon1.uasset'",
    ),
    filter_pattern: list[str] | None = typer.Option(
        None,
        "--filter-pattern",
        help="Extract only files matching this pattern (substring match). Can be specified"
        " multiple times. Example: --filter-pattern 'Subicons/'",
    ),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress all output except errors and warnings. Only errors will be printed"
        " to console.",
    ),
) -> None:
    """Extract assets from Foxhole PAK files."""
    from fs_tools.commands.uasset_extractor.uasset_extractor import run

    asyncio.run(
        run(
            pak=pak,
            catalog=catalog,
            extractor_tool=extractor_tool,
            converter_tool=converter_tool,
            output=output,
            workers=workers,
            filter_files=filter_files,
            filter_pattern=filter_pattern,
            log_file=log_file,
            verbose=verbose,
            quiet=quiet,
        )
    )


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


_ADD_MOD_EPILOG = """
This command runs the full pipeline to import a mod's icons into the database:
1. Extract assets from PAK files using repak
2. Convert UAsset files to PNG using umodel
3. Generate templates for all configured resolutions
4. Build/merge templates into the HDF5 database

Examples:
  # Add a mod to the database (using settings for tools and paths)
  fs-tools add-mod --pak /path/to/mod.pak --name "My Mod"

  # Add a mod with vanilla dependencies (for shared icons like crates)
  fs-tools add-mod --pak /path/to/mod.pak --name "My Mod" --vanilla /path/to/War.pak

  # Overwrite existing templates for this mod
  fs-tools add-mod --pak /path/to/mod.pak --name "My Mod" --overwrite

  # Add multiple PAK files for the same mod
  fs-tools add-mod --pak mod_part1.pak --pak mod_part2.pak --name "My Mod"

  # Extract assets to a directory for later reuse
  fs-tools add-mod --pak mod.pak --name "my-mod" --extract-dir ./extracted/my-mod --extract-only

  # Build database from previously extracted assets (no PAK extraction needed)
  fs-tools add-mod --name "my-mod" --extract-dir ./extracted/my-mod

  # Specify custom paths for all required files
  fs-tools add-mod --pak mod.pak --name "My Mod" \\
    --catalog /path/to/catalog.json \\
    --database /path/to/templates.h5 \\
    --extractor /path/to/repak.exe \\
    --converter /path/to/umodel.exe

Prerequisites:
  Before using this command, you need:
  1. repak.exe - PAK extractor (https://github.com/trumank/repak)
  2. umodel.exe - UAsset converter (https://www.gildor.org/en/projects/umodel)
  3. catalog.json - Item definitions file

  Configure these in your settings file or pass as arguments.
"""


@app.command("add-mod", epilog=_ADD_MOD_EPILOG)
def add_mod(
    name: str = typer.Option(
        ..., "--name", help="Name of the mod (alphanumeric, spaces, underscores, hyphens only)."
    ),
    pak: list[Path] | None = typer.Option(
        None,
        "--pak",
        help="Path to mod PAK file (can be specified multiple times for multi-PAK mods). Not"
        " required when using --extract-dir without --extract-only.",
    ),
    vanilla: Path | None = typer.Option(
        None,
        "--vanilla",
        help="Path to vanilla PAK file for shared dependencies (crate icons, subicons).",
    ),
    catalog: Path | None = typer.Option(
        None,
        "--catalog",
        help="Path to catalog.json (default: from database_builder.catalog_file setting).",
    ),
    database: Path | None = typer.Option(
        None,
        "--database",
        help="Path to output database (default: from scanner.database_path setting).",
    ),
    extractor: Path | None = typer.Option(
        None, "--extractor", help="Path to repak.exe (default: from external_tools.repak setting)."
    ),
    converter: Path | None = typer.Option(
        None,
        "--converter",
        help="Path to umodel.exe (default: from external_tools.umodel setting).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing templates for this mod (default: merge/skip existing).",
    ),
    resolution: list[str] | None = typer.Option(
        None,
        "--resolution",
        help="Target resolution (can be specified multiple times). If not specified, uses"
        " database_builder.target_resolutions setting or all resolutions.",
    ),
    extract_dir: Path | None = typer.Option(
        None,
        "--extract-dir",
        help="Directory for extracted assets. With --extract-only, assets are saved here."
        " Without --extract-only, assets are read from here (skipping extraction).",
    ),
    extract_only: bool = typer.Option(
        False,
        "--extract-only",
        help="Only extract assets to --extract-dir and stop. Does not generate templates or"
        " build database. Requires --extract-dir.",
    ),
    workers: int | None = typer.Option(
        None,
        "--workers",
        help="Number of worker processes for database building (default: from"
        " database_builder.workers setting or CPU count).",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress all output except errors."),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
) -> None:
    """Add mod content to a template database (full pipeline)."""
    from fs_tools.commands.add_mod.add_mod import run

    asyncio.run(
        run(
            mod_name=name,
            pak_files=pak,
            vanilla_pak=vanilla,
            catalog=catalog,
            database=database,
            extractor=extractor,
            converter=converter,
            overwrite=overwrite,
            resolutions=resolution,
            extract_dir=extract_dir,
            extract_only=extract_only,
            workers=workers,
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
