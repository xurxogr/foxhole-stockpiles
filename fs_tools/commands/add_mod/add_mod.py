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
from fs_tools.models.mod_import_result import ModImportResult
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


def _setup_run_logging(verbose: bool, quiet: bool, log_file: Path | None) -> None:
    """Configure logging for the add-mod pipeline.

    Args:
        verbose (bool): Enable debug-level logging.
        quiet (bool): Suppress all output except warnings/errors.
        log_file (Path | None): Path to log file (default: console only).
    """
    settings = get_settings()
    logging_settings = copy(settings.logging)
    if quiet:
        logging_settings.log_level = "WARNING"
    elif verbose:
        logging_settings.log_level = "DEBUG"
    logging_settings.log_file = str(log_file) if log_file else None
    setup_logging(logging_settings)


def _validate_extraction_args(
    pak_files: list[Path] | None,
    extract_dir: Path | None,
    extract_only: bool,
) -> bool:
    """Validate extraction-related arguments.

    Args:
        pak_files (list[Path] | None): Path(s) to mod PAK file(s).
        extract_dir (Path | None): Directory for extracted assets.
        extract_only (bool): Only extract assets and stop.

    Returns:
        bool: Whether pre-extracted assets are being used (extraction is skipped).

    Raises:
        typer.Exit: If validation fails.
    """
    if extract_only and not extract_dir:
        msg = "--extract-only requires --extract-dir to specify where to save assets"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    using_preextracted = bool(extract_dir and not extract_only)

    if not using_preextracted and not pak_files:
        msg = (
            "--pak is required unless using --extract-dir without --extract-only "
            "(pre-extracted assets mode)"
        )
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    return using_preextracted


def _resolve_extraction_tools(
    extractor: Path | None,
    converter: Path | None,
    pak_files: list[Path] | None,
    using_preextracted: bool,
) -> tuple[Path | None, Path | None]:
    """Resolve and validate the extractor/converter tools and PAK files.

    Args:
        extractor (Path | None): Path to repak.exe, if provided.
        converter (Path | None): Path to umodel.exe, if provided.
        pak_files (list[Path] | None): Path(s) to mod PAK file(s).
        using_preextracted (bool): Whether pre-extracted assets are being used.

    Returns:
        tuple[Path | None, Path | None]: Resolved (extractor_tool, converter_tool).

    Raises:
        typer.Exit: If validation fails.
    """
    settings = get_settings()
    extractor_tool = extractor or settings.external_tools.repak
    converter_tool = converter or settings.external_tools.umodel

    if using_preextracted:
        return extractor_tool, converter_tool

    if not extractor_tool:
        msg = "Extractor tool must be provided via --extractor or external_tools.repak setting"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    if not converter_tool:
        msg = "Converter tool must be provided via --converter or external_tools.umodel setting"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    for pak_file in pak_files or []:
        if not pak_file.exists():
            typer.echo(f"Error: PAK file not found: {pak_file}", err=True)
            raise typer.Exit(code=1)

    return extractor_tool, converter_tool


def _resolve_target_resolutions(resolutions: list[str] | None) -> list[str] | None:
    """Resolve and validate the target resolutions from args or settings.

    Args:
        resolutions (list[str] | None): Target resolution(s) from CLI args.

    Returns:
        list[str] | None: The resolved target resolutions.

    Raises:
        typer.Exit: If an invalid resolution is given.
    """
    if resolutions:
        target_resolutions: list[str] = []
        for res_str in resolutions:
            try:
                SupportedResolution(res_str)  # Validate
                target_resolutions.append(res_str)
            except ValueError:
                valid = [r.value for r in SupportedResolution]
                msg = f"Invalid resolution '{res_str}'. Valid resolutions: {', '.join(valid)}"
                typer.echo(msg, err=True)
                raise typer.Exit(code=2) from None
        return target_resolutions

    return get_settings().database_builder.target_resolutions


def _build_import_config(
    mod_name: str,
    pak_files: list[Path] | None,
    vanilla_pak: Path | None,
    catalog: Path | None,
    database: Path | None,
    extractor: Path | None,
    converter: Path | None,
    overwrite: bool,
    resolutions: list[str] | None,
    extract_dir: Path | None,
    extract_only: bool,
    workers: int | None,
) -> ModImportConfig:
    """Validate arguments and build the mod import configuration.

    Args:
        mod_name (str): Name of the mod (alphanumeric, spaces, underscores, hyphens only).
        pak_files (list[Path] | None): Path(s) to mod PAK file(s).
        vanilla_pak (Path | None): Path to vanilla PAK file for shared dependencies.
        catalog (Path | None): Path to catalog.json, if provided.
        database (Path | None): Path to output database, if provided.
        extractor (Path | None): Path to repak.exe, if provided.
        converter (Path | None): Path to umodel.exe, if provided.
        overwrite (bool): Overwrite existing templates for this mod.
        resolutions (list[str] | None): Target resolution(s) from CLI args.
        extract_dir (Path | None): Directory for extracted assets.
        extract_only (bool): Only extract assets and stop.
        workers (int | None): Number of worker processes for database building.

    Returns:
        ModImportConfig: The validated mod import configuration.

    Raises:
        typer.Exit: If validation fails.
    """
    settings = get_settings()

    using_preextracted = _validate_extraction_args(
        pak_files=pak_files, extract_dir=extract_dir, extract_only=extract_only
    )

    catalog_path = catalog or settings.database_builder.catalog_file
    if not catalog_path:
        msg = "Catalog path must be provided via --catalog or database_builder.catalog_file setting"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    database_path = database or settings.scanner.database_path
    if not extract_only and not database_path:
        msg = "Database path must be provided via --database or scanner.database_path setting"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    extractor_tool, converter_tool = _resolve_extraction_tools(
        extractor=extractor,
        converter=converter,
        pak_files=pak_files,
        using_preextracted=using_preextracted,
    )

    vanilla_pak_str = str(vanilla_pak) if vanilla_pak else None
    if vanilla_pak_str and not Path(vanilla_pak_str).exists():
        typer.echo(f"Error: Vanilla PAK file not found: {vanilla_pak_str}", err=True)
        raise typer.Exit(code=1)

    target_resolutions = _resolve_target_resolutions(resolutions)
    resolved_workers = workers if workers is not None else settings.database_builder.workers

    return ModImportConfig(
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


def _print_import_result(
    result: ModImportResult,
    mod_name: str,
    extract_only: bool,
    extract_dir: Path | None,
) -> None:
    """Print the outcome of a completed mod import.

    Args:
        result (ModImportProgress): The completed import result.
        mod_name (str): Name of the mod that was imported.
        extract_only (bool): Whether only extraction was performed.
        extract_dir (Path | None): Directory assets were extracted to.
    """
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
            print(f"  Templates skipped (already in database): {result.templates_skipped}")
    if result.warnings:
        print("  Warnings:")
        for warning in result.warnings:
            print(f"    - {warning}")


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
    _setup_run_logging(verbose=verbose, quiet=quiet, log_file=log_file)

    config = _build_import_config(
        mod_name=mod_name,
        pak_files=pak_files,
        vanilla_pak=vanilla_pak,
        catalog=catalog,
        database=database,
        extractor=extractor,
        converter=converter,
        overwrite=overwrite,
        resolutions=resolutions,
        extract_dir=extract_dir,
        extract_only=extract_only,
        workers=workers,
    )

    progress_callback = None if quiet else print_progress

    try:
        importer = ModImporter(config=config, progress_callback=progress_callback)
        result = await importer.run()

        if result.success:
            if not quiet:
                _print_import_result(
                    result=result,
                    mod_name=mod_name,
                    extract_only=extract_only,
                    extract_dir=extract_dir,
                )
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
    except Exception as e:  # noqa: BLE001 - surface any unexpected failure to the CLI user
        logger.exception("Unexpected error during import")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e
