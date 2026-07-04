"""Background worker for validating PAK files."""

import asyncio
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from fs_tools.commands.uasset_extractor.uasset_extractor import PakExtractor
from fs_tools.models.pak_validation_result import PakValidationResult

logger = logging.getLogger(__name__)


class PakValidationWorker(QThread):
    """Background worker thread for validating PAK files."""

    # Signal emitted when validation completes with the result
    validation_complete = Signal(object)  # PakValidationResult

    def __init__(
        self,
        pak_files: list[str],
        extractor_tool: Path,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the validation worker.

        Args:
            pak_files: List of PAK file paths to validate
            extractor_tool: Path to the repak extractor tool
            parent: Parent widget
        """
        super().__init__(parent)
        self.pak_files = pak_files
        self.extractor_tool = extractor_tool

    def run(self) -> None:
        """Run the validation in a background thread."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    PakExtractor.validate_required_assets(
                        pak_files=self.pak_files,
                        extractor_tool=self.extractor_tool,
                    )
                )
                self.validation_complete.emit(result)
            finally:
                loop.close()
        except Exception as e:  # noqa: BLE001 - report any failure via the validation result
            logger.error("PAK validation error: %s", e)
            # Create error result
            result = PakValidationResult()
            result.error_message = str(e)
            self.validation_complete.emit(result)
