"""Background worker that scans an image locally and routes it to outputs.

Two sources are supported: a screenshot file selected by the user, or a live
capture of the Foxhole window. Either way the OCR runs in-process via
:class:`LocalScanService` and the result is dispatched to the configured output
handlers, off the GUI thread.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.capture import capture_window, save_screenshot
from foxhole_stockpiles.services.local_scan import LocalScanService

logger = logging.getLogger(__name__)


class LocalScanWorker(QThread):
    """Scan a file or a live capture and emit the resulting stockpile.

    The completion signal is named ``scan_finished`` (not ``finished``) to avoid
    shadowing ``QThread``'s built-in ``finished`` signal.
    """

    scan_finished = Signal(object)  # Stockpile
    output_response = Signal(object)  # OutputResponse (dict | list[str] | None)
    scan_error = Signal(str)

    def __init__(
        self,
        service: LocalScanService,
        *,
        filepath: str | None = None,
        capture: bool = False,
        screenshots_folder: str = "",
    ) -> None:
        """Initialize the worker.

        Provide ``filepath`` to scan a file, or set ``capture`` to grab the live
        Foxhole window.

        Args:
            service (LocalScanService): The in-process scan service.
            filepath (str | None): Path to a screenshot file to scan.
            capture (bool): Capture the Foxhole window instead of reading a file.
            screenshots_folder (str): When capturing, save the screenshot here
                (empty disables saving).
        """
        super().__init__()
        self._service = service
        self._filepath = filepath
        self._capture = capture
        self._screenshots_folder = screenshots_folder

    def run(self) -> None:
        """Run the scan in the background thread."""
        try:
            if self._filepath is not None:
                stockpile: Stockpile
                response: object
                stockpile, response = self._service.scan(self._filepath)
            elif self._capture:
                image = capture_window()
                # Save the screenshot whether or not the scan succeeds — a failed
                # scan is exactly when the raw image is most useful to keep.
                try:
                    stockpile, response = self._service.scan(image)
                except Exception:
                    self._save_capture(image, None)
                    raise
                self._save_capture(image, stockpile)
            else:  # pragma: no cover - guarded by the caller
                raise ValueError("Either filepath or capture must be provided")
            self.scan_finished.emit(stockpile)
            self.output_response.emit(response)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.scan_error.emit(str(exc))

    def _save_capture(self, image: bytes, stockpile: Stockpile | None) -> None:
        """Save the captured screenshot if a folder is configured.

        A save failure is logged but does not fail the scan.

        Args:
            image (bytes): The captured PNG bytes.
            stockpile (Stockpile | None): The scan result (used for the
                filename), or None when the scan failed.
        """
        if not self._screenshots_folder:
            return
        try:
            save_screenshot(image, self._screenshots_folder, stockpile)
        except OSError as exc:
            logger.warning("Could not save screenshot to '%s': %s", self._screenshots_folder, exc)
