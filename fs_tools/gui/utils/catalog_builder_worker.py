"""Background worker for catalog builder process."""

import asyncio
import json
import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from fs_tools.services.catalog_builder import (
    BlueprintExtractor,
    CatalogAssembler,
    CatalogPreset,
    CatalogRuleSet,
    apply_rules,
    preset_ruleset,
)

logger = logging.getLogger(__name__)


class CatalogBuilderWorker(QThread):
    """Worker thread for catalog builder process.

    Runs the complete catalog building pipeline:
    1. Extract blueprints from PAK file
    2. Convert uasset files to JSON
    3. Build catalog from extracted data
    4. Write catalog to output file
    """

    finished = Signal(bool)  # Emits True on success, False on failure/cancel
    error = Signal(str)  # Emits error message
    progress = Signal(str)  # Emits progress message for UI updates

    def __init__(
        self,
        pak_file: Path,
        output_path: Path,
        extractor_tool: Path,
        converter_tool: Path,
        workers: int = 4,
        ruleset: CatalogRuleSet | None = None,
    ) -> None:
        """Initialize the catalog builder worker.

        Args:
            pak_file (Path): Path to the PAK file
            output_path (Path): Path for the output catalog.json
            extractor_tool (Path): Path to repak executable
            converter_tool (Path): Path to UAssetGUI executable
            workers (int): Number of parallel workers for conversion
            ruleset (CatalogRuleSet | None): Field rules to project the catalog
                through. Defaults to the FULL preset (keep everything).
        """
        super().__init__()
        self.pak_file = pak_file
        self.output_path = output_path
        self.extractor_tool = extractor_tool
        self.converter_tool = converter_tool
        self.workers = workers
        self.ruleset = ruleset if ruleset is not None else preset_ruleset(CatalogPreset.FULL)
        self._should_stop = False

        logger.debug(
            "CatalogBuilderWorker initialized: pak=%s, output=%s",
            pak_file,
            output_path,
        )

    def stop(self) -> None:
        """Request the worker to stop."""
        self._should_stop = True
        logger.info("Catalog builder worker stop requested")

    def run(self) -> None:
        """Run the catalog building process."""
        try:
            # Run the async build process
            asyncio.run(self._build_catalog())
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            logger.error("Catalog builder failed: %s", e)
            logger.debug("Traceback: %s", traceback.format_exc())
            self.error.emit(str(e))
            self.finished.emit(False)

    async def _build_catalog(self) -> None:
        """Build the catalog asynchronously."""
        try:
            # Step 1: Extract from PAK
            self.progress.emit("Extracting blueprints from PAK file...")
            logger.info("Starting PAK extraction: %s", self.pak_file)

            if self._should_stop:
                logger.info("Build cancelled during extraction setup")
                self.finished.emit(False)
                return

            extractor = BlueprintExtractor(
                pak_file=self.pak_file,
                extractor_tool=self.extractor_tool,
                converter_tool=self.converter_tool,
                max_workers=self.workers,
                force_extract=False,
                extraction_dir=None,  # Use temp directory
            )

            extract_dir = await extractor.extract()

            if self._should_stop:
                logger.info("Build cancelled after extraction")
                self.finished.emit(False)
                return

            logger.info(
                "Extraction complete: %d files extracted, %d converted",
                extractor.stats["extracted"],
                extractor.stats["converted"],
            )
            self.progress.emit(
                f"Extracted {extractor.stats['extracted']} files, "
                f"converted {extractor.stats['converted']} to JSON"
            )

            # Step 2: Build catalog
            self.progress.emit("Building catalog from extracted data...")
            logger.info("Building catalog from: %s", extract_dir)

            if self._should_stop:
                logger.info("Build cancelled before catalog assembly")
                self.finished.emit(False)
                return

            assembler = CatalogAssembler.from_extract_dir(extract_dir)
            catalog = assembler.build_catalog()

            if self._should_stop:
                logger.info("Build cancelled after catalog assembly")
                self.finished.emit(False)
                return

            stats = assembler.get_stats()
            logger.info(
                "Catalog built: %d files parsed, %d stockpilable items, %d errors",
                stats["parsed"],
                stats["stockpilable"],
                stats["errors"],
            )
            self.progress.emit(f"Built catalog: {stats['stockpilable']} stockpilable items")

            # Project the catalog through the selected field rules (an empty rule
            # set is identity; the FS preset deep-prunes each item).
            catalog = apply_rules(catalog, self.ruleset)
            logger.info(
                "Applied %d catalog rule(s): %d items", len(self.ruleset.rules), len(catalog)
            )

            # Step 3: Write output
            self.progress.emit(f"Writing catalog to {self.output_path}...")
            logger.info("Writing catalog to: %s", self.output_path)

            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, sort_keys=True, ensure_ascii=False)

            self.progress.emit(f"Catalog saved: {len(catalog)} items written to {self.output_path}")
            logger.info("Catalog written successfully: %d items", len(catalog))

            self.finished.emit(True)

        except Exception as e:
            logger.error("Catalog build failed: %s", e)
            logger.debug("Traceback: %s", traceback.format_exc())
            self.error.emit(str(e))
            self.finished.emit(False)
