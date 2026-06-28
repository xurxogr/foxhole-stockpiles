"""Worker threads for clipboard stockpile-export processing."""

import asyncio
import logging

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.services.clipboard_scan import ClipboardScanService

logger = logging.getLogger(__name__)


class ClipboardScanWorker(QThread):
    """Worker thread for a one-shot clipboard read (manual mode)."""

    finished = Signal(bool)  # True = success, False = failure
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
            self.finished.emit(True)
        except Exception as e:  # noqa: BLE001 - surface any failure to the log
            self.error.emit(f"Error reading clipboard: {e}")
            self.finished.emit(False)


class ClipboardMonitorWorker(QThread):
    """Worker thread for continuous clipboard monitoring (monitor mode)."""

    finished = Signal(bool)  # True = stopped normally, False = error
    error = Signal(str)  # Error message
    stockpile_found = Signal(object)  # Stockpile emitted on each new export
    output_response = Signal(object)  # OutputResponse (dict | list[str] | None)

    def __init__(self, service: ClipboardScanService, poll_interval: float = 1.0) -> None:
        """Initialize the clipboard monitor worker.

        Args:
            service (ClipboardScanService): The clipboard scan service to use.
            poll_interval (float): Polling interval in seconds.
        """
        super().__init__()
        self._service = service
        self._poll_interval = poll_interval
        self._should_stop = False

    def stop(self) -> None:
        """Request the monitor to stop."""
        self._should_stop = True

    def run(self) -> None:
        """Poll the clipboard for new exports until stopped."""
        try:
            logger.info("Starting clipboard monitor (poll: %ss)", self._poll_interval)
            asyncio.run(self._loop())
            logger.info("Clipboard monitor stopped")
            self.finished.emit(True)
        except Exception as e:  # noqa: BLE001 - surface any failure to the log
            self.error.emit(f"Error monitoring clipboard: {e}")
            self.finished.emit(False)

    async def _loop(self) -> None:
        """Run the polling loop, emitting each new parsed stockpile."""
        while not self._should_stop:
            await asyncio.sleep(self._poll_interval)
            if self._should_stop:
                break
            try:
                stockpile = await self._service.poll()
                if stockpile is not None:
                    self.stockpile_found.emit(stockpile)
                    self.output_response.emit(self._service.last_output)
            except Exception as e:  # noqa: BLE001 - keep monitoring despite errors
                logger.error("Clipboard monitor error: %s", e)
