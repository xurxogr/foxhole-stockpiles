"""Command for adding a mod to the template database.

This command runs the full pipeline to import a mod:
1. Extract assets from PAK files
2. Generate templates from extracted assets
3. Build/merge database with new templates
"""

import argparse
import asyncio
import logging
import sys
from copy import copy
from pathlib import Path

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


async def main() -> None:
    """Main entry point for add-mod command."""
    parser = argparse.ArgumentParser(
        description="Add a mod to the template database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This command runs the full pipeline to import a mod's icons into the database:
1. Extract assets from PAK files using repak
2. Convert UAsset files to PNG using umodel
3. Generate templates for all configured resolutions
4. Build/merge templates into the HDF5 database

Examples:
  # Add a mod to the database (using settings for tools and paths)
  fs add-mod --pak /path/to/mod.pak --name "My Mod"

  # Add a mod with vanilla dependencies (for shared icons like crates)
  fs add-mod --pak /path/to/mod.pak --name "My Mod" --vanilla /path/to/War.pak

  # Overwrite existing templates for this mod
  fs add-mod --pak /path/to/mod.pak --name "My Mod" --overwrite

  # Add multiple PAK files for the same mod
  fs add-mod --pak mod_part1.pak --pak mod_part2.pak --name "My Mod"

  # Extract assets to a directory for later reuse
  fs add-mod --pak mod.pak --name "my-mod" --extract-dir ./extracted/my-mod --extract-only

  # Build database from previously extracted assets (no PAK extraction needed)
  fs add-mod --name "my-mod" --extract-dir ./extracted/my-mod

  # Specify custom paths for all required files
  fs add-mod --pak mod.pak --name "My Mod" \\
    --catalog /path/to/catalog.json \\
    --database /path/to/templates.h5 \\
    --extractor /path/to/repak.exe \\
    --converter /path/to/umodel.exe

Prerequisites:
  Before using this command, you need:
  1. repak.exe - PAK extractor (https://github.com/trumank/repak)
  2. umodel.exe - UAsset converter (https://www.gildor.org/en/projects/umodel)
  3. catalog.json - Item definitions file

  Configure these in your .fs_config settings file or pass as arguments.
        """,
    )

    # PAK files (required unless using pre-extracted assets)
    parser.add_argument(
        "--pak",
        type=Path,
        action="append",
        dest="pak_files",
        help="Path to mod PAK file (can be specified multiple times for multi-PAK mods). "
        "Not required when using --extract-dir without --extract-only.",
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        dest="mod_name",
        help="Name of the mod (alphanumeric, spaces, underscores, hyphens only)",
    )

    # Optional paths (fall back to settings)
    parser.add_argument(
        "--vanilla",
        type=Path,
        dest="vanilla_pak",
        help="Path to vanilla PAK file for shared dependencies (crate icons, subicons)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Path to catalog.json (default: from database_builder.catalog_file setting)",
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="Path to output database (default: from scanner.database_path setting)",
    )
    parser.add_argument(
        "--extractor",
        type=Path,
        help="Path to repak.exe (default: from external_tools.repak setting)",
    )
    parser.add_argument(
        "--converter",
        type=Path,
        help="Path to umodel.exe (default: from external_tools.umodel setting)",
    )

    # Behavior options
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing templates for this mod (default: merge/skip existing)",
    )
    parser.add_argument(
        "--resolution",
        action="append",
        dest="resolutions",
        help=(
            "Target resolution (can be specified multiple times). "
            "If not specified, uses database_builder.target_resolutions setting or all resolutions."
        ),
    )

    # Extraction options
    parser.add_argument(
        "--extract-dir",
        type=Path,
        dest="extract_dir",
        help=(
            "Directory for extracted assets. With --extract-only, assets are saved here. "
            "Without --extract-only, assets are read from here (skipping extraction)."
        ),
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        dest="extract_only",
        help=(
            "Only extract assets to --extract-dir and stop. "
            "Does not generate templates or build database. Requires --extract-dir."
        ),
    )

    # Performance options
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes for database building "
        "(default: from database_builder.workers setting or CPU count)",
    )

    # Logging options
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (debug level)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Path to log file (default: console only)",
    )

    args = parser.parse_args()

    # Load settings
    settings = get_settings()

    # Setup logging
    logging_settings = copy(settings.logging)
    if args.quiet:
        logging_settings.log_level = "WARNING"
    elif args.verbose:
        logging_settings.log_level = "DEBUG"
    logging_settings.log_file = args.log_file
    setup_logging(logging_settings)

    # Validate extraction options
    if args.extract_only and not args.extract_dir:
        parser.error("--extract-only requires --extract-dir to specify where to save assets")

    # Determine if we're using pre-extracted assets (no extraction needed)
    using_preextracted = args.extract_dir and not args.extract_only

    # PAK files are required unless using pre-extracted assets
    if not using_preextracted and not args.pak_files:
        parser.error(
            "--pak is required unless using --extract-dir without --extract-only "
            "(pre-extracted assets mode)"
        )

    # Resolve paths from args or settings
    catalog_path = args.catalog or settings.database_builder.catalog_file
    if not catalog_path:
        parser.error(
            "Catalog path must be provided via --catalog or database_builder.catalog_file setting"
        )

    # Database path not required for extract-only mode
    database_path = args.database or settings.scanner.database_path
    if not args.extract_only and not database_path:
        parser.error(
            "Database path must be provided via --database or scanner.database_path setting"
        )

    # Extractor and converter tools only required when extracting
    extractor_tool = args.extractor or settings.external_tools.repak
    converter_tool = args.converter or settings.external_tools.umodel

    if not using_preextracted:
        if not extractor_tool:
            parser.error(
                "Extractor tool must be provided via --extractor or external_tools.repak setting"
            )

        if not converter_tool:
            parser.error(
                "Converter tool must be provided via --converter or external_tools.umodel setting"
            )

        # Validate PAK files exist
        for pak_file in args.pak_files:
            if not pak_file.exists():
                print(f"Error: PAK file not found: {pak_file}", file=sys.stderr)
                sys.exit(1)

    # Validate vanilla PAK if provided
    vanilla_pak = str(args.vanilla_pak) if args.vanilla_pak else None
    if vanilla_pak and not Path(vanilla_pak).exists():
        print(f"Error: Vanilla PAK file not found: {vanilla_pak}", file=sys.stderr)
        sys.exit(1)

    # Parse and validate resolutions
    target_resolutions: list[str] | None = None
    if args.resolutions:
        target_resolutions = []
        for res_str in args.resolutions:
            try:
                SupportedResolution(res_str)  # Validate
                target_resolutions.append(res_str)
            except ValueError:
                valid = [r.value for r in SupportedResolution]
                parser.error(
                    f"Invalid resolution '{res_str}'. Valid resolutions: {', '.join(valid)}"
                )
    elif settings.database_builder.target_resolutions:
        target_resolutions = settings.database_builder.target_resolutions

    # Resolve workers from args or settings
    workers = args.workers if args.workers is not None else settings.database_builder.workers

    # Create configuration
    config = ModImportConfig(
        mod_pak_files=[str(p) for p in args.pak_files] if args.pak_files else [],
        mod_name=args.mod_name,
        catalog_path=catalog_path,
        overwrite=args.overwrite,
        vanilla_pak_file=vanilla_pak,
        extractor_tool=extractor_tool,
        converter_tool=converter_tool,
        database_path=database_path,
        target_resolutions=target_resolutions,
        template_settings=TemplateSettings(),
        database_workers=workers,
        extract_dir=args.extract_dir,
        extract_only=args.extract_only,
    )

    # Run import
    progress_callback = None if args.quiet else print_progress

    try:
        importer = ModImporter(config=config, progress_callback=progress_callback)
        result = await importer.run()

        if result.success:
            if not args.quiet:
                print()
                if args.extract_only:
                    print(f"Successfully extracted mod '{args.mod_name}'")
                    if result.templates_added > 0:
                        print(f"  Assets extracted: {result.templates_added}")
                    print(f"  Output directory: {args.extract_dir}")
                else:
                    print(f"Successfully imported mod '{args.mod_name}'")
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
            print(f"Error: {result.error_message}", file=sys.stderr)
            sys.exit(1)

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error during import")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
