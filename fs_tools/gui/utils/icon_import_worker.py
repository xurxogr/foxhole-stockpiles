"""Background worker for icon import process."""

import asyncio
import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.core.settings import get_settings
from fs_tools.core.settings.sections.templates import TemplateSettings
from fs_tools.models.mod_import_config import ModImportConfig
from fs_tools.models.mod_import_progress import ModImportProgress
from fs_tools.services.mod_importer import ModImporter

logger = logging.getLogger(__name__)


class IconImportWorker(QThread):
    """Worker thread for icon import process.

    Runs the complete pipeline using the ModImporter service:
    1. Extract assets from PAK files (uasset_extractor)
    2. Generate templates (generate_templates)
    3. Build/update database (database_builder)

    All intermediate files are stored in temporary directories and cleaned up automatically.
    """

    finished = Signal(bool)  # Emits True on success, False on failure/cancel
    error = Signal(str)  # Emits error message
    progress = Signal(int, str)  # Emits (step_number, message) for UI updates

    def __init__(
        self,
        mod_pak_files: list[str],
        mod_name: str,
        catalog_path: Path,
        overwrite: bool = False,
        vanilla_pak_file: str | None = None,
        database_path: Path | None = None,
        database_workers: int | None = None,
    ) -> None:
        """Initialize the icon import worker.

        Args:
            mod_pak_files (list[str]): List of mod PAK file paths
            mod_name (str): Name of the mod
            catalog_path (Path): Path to catalog.json file
            overwrite (bool): Whether to overwrite existing data
            vanilla_pak_file (str | None): Optional vanilla PAK file for dependencies
            database_path (Path | None): Optional database path (uses settings if None)
            database_workers (int | None): Number of workers for database building.
                Set to 1 to disable multiprocessing (recommended for GUI on Windows).

        Raises:
            ValueError: If mod_name is invalid or contains unsafe characters
        """
        super().__init__()
        self.mod_pak_files = mod_pak_files
        # Validate mod name early (fail fast)
        self.mod_name = ModImporter._validate_mod_name(mod_name)
        self.catalog_path = catalog_path
        self.overwrite = overwrite
        self.vanilla_pak_file = vanilla_pak_file
        self.database_path = database_path
        self.database_workers = database_workers
        self._should_stop = False

        # Get settings
        self.settings = get_settings()

        logger.debug(
            "IconImportWorker initialized: mod=%s, paks=%d, vanilla=%s, db=%s",
            self.mod_name,
            len(mod_pak_files),
            "Yes" if vanilla_pak_file else "No",
            database_path or "default",
        )

    def stop(self) -> None:
        """Request the worker to stop."""
        self._should_stop = True

    def _on_progress(self, progress_info: ModImportProgress) -> None:
        """Handle progress updates from ModImporter.

        Args:
            progress_info: Progress information from the importer
        """
        # Emit progress signal for UI updates
        self.progress.emit(progress_info.current_step, progress_info.message)

    def _check_cancel(self) -> bool:
        """Check if worker should be cancelled.

        Returns:
            bool: True if worker should stop
        """
        return self._should_stop

    def run(self) -> None:
        """Run the icon import process in background thread."""
        try:
            # Run async operations
            asyncio.run(self._run_import())
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            logger.exception("Icon import failed with exception")
            self.error.emit(str(e))
            self.finished.emit(False)

    async def _run_import(self) -> None:
        """Run the import using ModImporter service."""
        success = False

        try:
            # Build configuration from settings
            external_tools = self.settings.external_tools
            db_builder = self.settings.database_builder
            # Use custom database path if provided, otherwise fall back to settings
            database_path = self.database_path or self.settings.scanner.database_path
            config = ModImportConfig(
                mod_pak_files=self.mod_pak_files,
                mod_name=self.mod_name,
                catalog_path=self.catalog_path,
                overwrite=self.overwrite,
                vanilla_pak_file=self.vanilla_pak_file,
                extractor_tool=external_tools.repak,
                converter_tool=external_tools.umodel,
                database_path=database_path,
                target_resolutions=db_builder.target_resolutions,
                template_settings=TemplateSettings(),
                database_workers=self.database_workers,
            )

            # Create importer with callbacks
            importer = ModImporter(
                config=config,
                progress_callback=self._on_progress,
                cancel_check=self._check_cancel,
            )

            # Run the import
            result = await importer.run()

            if result.success:
                success = True
                logger.info("Icon import completed successfully")
            else:
                # Emit detailed error message
                error_msg = result.error_message or "Unknown error"
                self.error.emit(error_msg)
                logger.error("Icon import failed: %s", error_msg)

            # Log any warnings
            for warning in result.warnings:
                logger.warning("Import warning: %s", warning)

        except Exception as e:
            logger.exception("Error in import pipeline")
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else "No error message provided"
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            detailed_error = f"{error_type}: {error_msg}\n\nTraceback:\n{tb}"
            self.error.emit(detailed_error)

        finally:
            self.finished.emit(success and not self._should_stop)
