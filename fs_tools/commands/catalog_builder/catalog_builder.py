"""Catalog builder command for Foxhole stockpile items.

This module builds catalog files from PAK files by:
1. Extracting needed directories from PAK using repak
2. Converting .uasset files to .json using UAssetGUI
3. Building the catalog using CatalogAssembler
"""

import json
import logging
from copy import copy
from pathlib import Path

import typer

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from fs_tools.services.catalog_builder import (
    BlueprintExtractor,
    CatalogAssembler,
)

DEFAULT_PAK_FILE = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Foxhole\War\Content\Paks"
    r"\War-WindowsNoEditor.pak"
)
DEFAULT_EXTRACTOR = r"C:\repak\repak.exe"
DEFAULT_CONVERTER = r"C:\UAssetGUI\UAssetGUI.exe"
DEFAULT_OUTPUT = "catalog.json"


async def run(
    pak: Path = Path(DEFAULT_PAK_FILE),
    extractor: Path = Path(DEFAULT_EXTRACTOR),
    converter: Path = Path(DEFAULT_CONVERTER),
    output: Path = Path(DEFAULT_OUTPUT),
    keep_temp: bool = False,
    force_extract: bool = False,
    workers: int = 4,
    log_file: Path | None = None,
    verbose: bool = False,
    quiet: bool = False,
    extract_dir: Path | None = None,
) -> None:
    """Build catalog from Foxhole PAK file.

    Args:
        pak (Path): Path to War-WindowsNoEditor.pak file.
        extractor (Path): Path to repak.exe extraction tool.
        converter (Path): Path to UAssetGUI.exe conversion tool.
        output (Path): Output path for catalog JSON.
        keep_temp (bool): Keep temporary extraction directory. Defaults to False.
        force_extract (bool): Force re-extraction from PAK even if JSON files
            exist. Defaults to False.
        workers (int): Number of parallel conversions. Defaults to 4.
        log_file (Path | None): Path to log file (default: console only).
        verbose (bool): Enable verbose logging (debug level). Defaults to False.
        quiet (bool): Suppress all output except errors. Defaults to False.
        extract_dir (Path | None): Use existing extraction directory instead of
            extracting from PAK (e.g., war/).
    """
    # Setup logging
    settings = copy(get_settings())
    logging_settings = settings.logging

    if quiet:
        logging_settings.log_level = "WARNING"
    elif verbose:
        logging_settings.log_level = "DEBUG"

    logging_settings.log_file = str(log_file) if log_file is not None else None
    setup_logging(logging_settings)

    logger = logging.getLogger(__name__)

    # Get extraction directory
    if extract_dir:
        resolved_extract_dir = extract_dir
        logger.debug("Using provided extraction directory: %s", resolved_extract_dir)
    else:
        # Extract from PAK
        # Use temp directory if --keep-temp, otherwise cache in "war/" directory
        extraction_dir = None if keep_temp else Path("war")
        blueprint_extractor = BlueprintExtractor(
            pak_file=pak,
            extractor_tool=extractor,
            converter_tool=converter,
            max_workers=workers,
            force_extract=force_extract,
            extraction_dir=extraction_dir,
        )

        resolved_extract_dir = await blueprint_extractor.extract()

        logger.debug(
            "Files extracted: %d, converted: %d",
            blueprint_extractor.stats["extracted"],
            blueprint_extractor.stats["converted"],
        )

    # Build catalog using service
    logger.info("Building catalog...")
    try:
        service = CatalogAssembler.from_extract_dir(resolved_extract_dir)
    except (FileNotFoundError, NotADirectoryError) as e:
        logger.error("Invalid extraction directory: %s", e)
        raise typer.Exit(code=1) from e

    catalog = service.build_catalog()

    # Write output (sorted keys for easier comparison)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, sort_keys=True, ensure_ascii=False)

    # Print summary
    stats = service.get_stats()
    logger.info(
        "Catalog Build Summary. Files parsed: %d, Stockpilable items: %d, "
        "Errors: %d. written to %s",
        stats["parsed"],
        stats["stockpilable"],
        stats["errors"],
        output,
    )
