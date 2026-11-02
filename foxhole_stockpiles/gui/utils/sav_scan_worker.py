"""Worker thread for one-time SAV file scanning."""

import asyncio
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor

logger = logging.getLogger(__name__)


class SavScanWorker(QThread):
    """Worker thread for one-time SAV file scanning.

    The completion signal is named ``scan_finished`` (not ``finished``) to avoid
    shadowing ``QThread``'s built-in ``finished`` signal.
    """

    scan_finished = Signal(bool)  # True = success, False = failure
    error = Signal(str)  # Error message
    progress = Signal(str)  # Progress message
    stockpiles_found = Signal(list)  # List of Stockpile objects
    output_response = Signal(object)  # OutputResponse (dict | list[str] | None)

    def __init__(
        self,
        sav_path: Path,
        output_coordinator: OutputCoordinator,
    ) -> None:
        """Initialize the SAV scan worker.

        Args:
            sav_path (Path): Path to the .sav file to scan.
            output_coordinator (OutputCoordinator): Output coordinator for handlers.
        """
        super().__init__()
        self._sav_path = sav_path
        self._output_coordinator = output_coordinator

    def run(self) -> None:
        """Run the scan in background thread."""
        try:
            logger.info("Processing file: %s", self._sav_path)
            self.progress.emit(f"Processing: {self._sav_path.name}")

            processor = SaveFileProcessor(
                file_path=self._sav_path,
                output_coordinator=self._output_coordinator,
                emit_all_on_start=True,
            )

            stockpiles = asyncio.run(processor.run_once())

            self.stockpiles_found.emit(stockpiles)
            self.output_response.emit(processor.last_output)
            self.scan_finished.emit(True)

        except RuntimeError as e:
            self.error.emit(str(e))
            self.scan_finished.emit(False)
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            self.error.emit(f"Error processing SAV file: {e}")
            self.scan_finished.emit(False)
