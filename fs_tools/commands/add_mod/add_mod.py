"""Command for adding a mod to the template database.

This command runs the full pipeline to import a mod:
1. Extract assets from PAK files
2. Generate templates from extracted assets
3. Build/merge database with new templates
"""

import logging
import sys
from copy import copy
from pathlib import Path

import typer

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.core.settings.sections.templates import TemplateSettings
from fs_tools.models.mod_import_config import ModImportConfig
from fs_tools.models.mod_import_progress import ModImportProgress
from fs_tools.services.mod_importer import ModImporter

logger = logging.getLogger(__name__)


def print_progress(progress: ModImportProgress) -> None:
    """Print progress to console.

    Args:
        progress: Progress information
    """
    if progress.is_error:
        print(f"ERROR: {progress.error_message}", file=sys.stderr)
    elif progress.is_complete:
        print(f"[{progress.current_step}/{progress.total_steps}] {progress.message}")
    else:
        step = f"[{progress.current_step}/{progress.total_steps}]"
        print(f"{step} {progress.step_name}: {progress.message}")


async def run(
    mod_name: str,
    pak_files: list[Path] | None = None,
    vanilla_pak: Path | None = None,
    catalog: Path | None = None,
    database: Path | None = None,
    extractor: Path | None = None,
    converter: Path | None = None,
    overwrite: bool = False,
    resolutions: list[str] | None = None,
    extract_dir: Path | None = None,
    extract_only: bool = False,
    workers: int | None = None,
    verbose: bool = False,
    quiet: bool = False,
    log_file: Path | None = None,
) -> None:
    """Run the add-mod pipeline to import a mod into the template database.

    This command runs the full pipeline to import a mod's icons into the database:
    1. Extract assets from PAK files using repak
    2. Convert UAsset files to PNG using umodel
    3. Generate templates for all configured resolutions
    4. Build/merge templates into the HDF5 database

    Args:
        mod_name (str): Name of the mod (alphanumeric, spaces, underscores, hyphens only).
        pak_files (list[Path] | None): Path(s) to mod PAK file(s) (can be specified multiple
            times for multi-PAK mods). Not required when using extract_dir without
            extract_only. Defaults to None.
        vanilla_pak (Path | None): Path to vanilla PAK file for shared dependencies (crate
            icons, subicons). Defaults to None.
        catalog (Path | None): Path to catalog.json (default: from
            database_builder.catalog_file setting). Defaults to None.
        database (Path | None): Path to output database (default: from
            scanner.database_path setting). Defaults to None.
        extractor (Path | None): Path to repak.exe (default: from external_tools.repak
            setting). Defaults to None.
        converter (Path | None): Path to umodel.exe (default: from external_tools.umodel
            setting). Defaults to None.
        overwrite (bool): Overwrite existing templates for this mod (default:
            merge/skip existing). Defaults to False.
        resolutions (list[str] | None): Target resolution(s) (can be specified multiple
            times). If not specified, uses database_builder.target_resolutions setting or
            all resolutions. Defaults to None.
        extract_dir (Path | None): Directory for extracted assets. With extract_only,
            assets are saved here. Without extract_only, assets are read from here
            (skipping extraction). Defaults to None.
        extract_only (bool): Only extract assets to extract_dir and stop. Does not
            generate templates or build database. Requires extract_dir. Defaults to False.
        workers (int | None): Number of worker processes for database building (default:
            from database_builder.workers setting or CPU count). Defaults to None.
        verbose (bool): Enable verbose logging (debug level). Defaults to False.
        quiet (bool): Suppress all output except errors. Defaults to False.
        log_file (Path | None): Path to log file (default: console only). Defaults to None.

    Raises:
        typer.Exit: If validation fails or the import encounters an error.
    """
    # Load settings
    settings = get_settings()

    # Setup logging
    logging_settings = copy(settings.logging)
    if quiet:
        logging_settings.log_level = "WARNING"
    elif verbose:
        logging_settings.log_level = "DEBUG"
    logging_settings.log_file = str(log_file) if log_file else None
    setup_logging(logging_settings)

    # Validate extraction options
    if extract_only and not extract_dir:
        msg = "--extract-only requires --extract-dir to specify where to save assets"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    # Determine if we're using pre-extracted assets (no extraction needed)
    using_preextracted = bool(extract_dir and not extract_only)

    # PAK files are required unless using pre-extracted assets
    if not using_preextracted and not pak_files:
        msg = (
            "--pak is required unless using --extract-dir without --extract-only "
            "(pre-extracted assets mode)"
        )
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    # Resolve paths from args or settings
    catalog_path = catalog or settings.database_builder.catalog_file
    if not catalog_path:
        msg = "Catalog path must be provided via --catalog or database_builder.catalog_file setting"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    # Database path not required for extract-only mode
    database_path = database or settings.scanner.database_path
    if not extract_only and not database_path:
        msg = "Database path must be provided via --database or scanner.database_path setting"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    # Extractor and converter tools only required when extracting
    extractor_tool = extractor or settings.external_tools.repak
    converter_tool = converter or settings.external_tools.umodel

    if not using_preextracted:
        if not extractor_tool:
            msg = "Extractor tool must be provided via --extractor or external_tools.repak setting"
            typer.echo(msg, err=True)
            raise typer.Exit(code=2)

        if not converter_tool:
            msg = "Converter tool must be provided via --converter or external_tools.umodel setting"
            typer.echo(msg, err=True)
            raise typer.Exit(code=2)

        # Validate PAK files exist
        for pak_file in pak_files or []:
            if not pak_file.exists():
                typer.echo(f"Error: PAK file not found: {pak_file}", err=True)
                raise typer.Exit(code=1)

    # Validate vanilla PAK if provided
    vanilla_pak_str = str(vanilla_pak) if vanilla_pak else None
    if vanilla_pak_str and not Path(vanilla_pak_str).exists():
        typer.echo(f"Error: Vanilla PAK file not found: {vanilla_pak_str}", err=True)
        raise typer.Exit(code=1)

    # Parse and validate resolutions
    target_resolutions: list[str] | None = None
    if resolutions:
        target_resolutions = []
        for res_str in resolutions:
            try:
                SupportedResolution(res_str)  # Validate
                target_resolutions.append(res_str)
            except ValueError:
                valid = [r.value for r in SupportedResolution]
                msg = f"Invalid resolution '{res_str}'. Valid resolutions: {', '.join(valid)}"
                typer.echo(msg, err=True)
                raise typer.Exit(code=2) from None
    elif settings.database_builder.target_resolutions:
        target_resolutions = settings.database_builder.target_resolutions

    # Resolve workers from args or settings
    resolved_workers = workers if workers is not None else settings.database_builder.workers

    # Create configuration
    config = ModImportConfig(
        mod_pak_files=[str(p) for p in pak_files] if pak_files else [],
        mod_name=mod_name,
        catalog_path=catalog_path,
        overwrite=overwrite,
        vanilla_pak_file=vanilla_pak_str,
        extractor_tool=extractor_tool,
        converter_tool=converter_tool,
        database_path=database_path,
        target_resolutions=target_resolutions,
        template_settings=TemplateSettings(),
        database_workers=resolved_workers,
        extract_dir=extract_dir,
        extract_only=extract_only,
    )

    # Run import
    progress_callback = None if quiet else print_progress

    try:
        importer = ModImporter(config=config, progress_callback=progress_callback)
        result = await importer.run()

        if result.success:
            if not quiet:
                print()
                if extract_only:
                    print(f"Successfully extracted mod '{mod_name}'")
                    if result.templates_added > 0:
                        print(f"  Assets extracted: {result.templates_added}")
                    print(f"  Output directory: {extract_dir}")
                else:
                    print(f"Successfully imported mod '{mod_name}'")
                    if result.templates_added > 0:
                        print(f"  Templates added: {result.templates_added}")
                    if result.templates_skipped > 0:
                        print(
                            f"  Templates skipped (already in database): {result.templates_skipped}"
                        )
                if result.warnings:
                    print("  Warnings:")
                    for warning in result.warnings:
                        print(f"    - {warning}")
        else:
            typer.echo(f"Error: {result.error_message}", err=True)
            raise typer.Exit(code=1)

    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except FileNotFoundError as e:
        typer.echo(f"File not found: {e}", err=True)
        raise typer.Exit(code=1) from e
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Unexpected error during import")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e
