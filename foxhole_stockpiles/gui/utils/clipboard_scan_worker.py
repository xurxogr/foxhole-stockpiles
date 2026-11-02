"""Worker thread for a one-shot clipboard read."""

import asyncio

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.services.clipboard_scan import ClipboardScanService


class ClipboardScanWorker(QThread):
    """Worker thread for a one-shot clipboard read (manual mode).

    The completion signal is named ``scan_finished`` (not ``finished``) to avoid
    shadowing ``QThread``'s built-in ``finished`` signal.
    """

    scan_finished = Signal(bool)  # True = success, False = failure
    error = Signal(str)  # Error message
    stockpile_found = Signal(object)  # Stockpile | None
    output_response = Signal(object)  # OutputResponse (dict | list[str] | None)

    def __init__(self, service: ClipboardScanService) -> None:
        """Initialize the one-shot clipboard scan worker.

        Args:
            service (ClipboardScanService): The clipboard scan service to use.
        """
        super().__init__()
        self._service = service

    def run(self) -> None:
        """Read and parse the current clipboard once in a background thread."""
        try:
            stockpile = asyncio.run(self._service.scan_once())
            self.stockpile_found.emit(stockpile)
            self.output_response.emit(self._service.last_output)
            self.scan_finished.emit(True)
        except Exception as e:  # noqa: BLE001 - surface any failure to the log
            self.error.emit(f"Error reading clipboard: {e}")
            self.scan_finished.emit(False)
