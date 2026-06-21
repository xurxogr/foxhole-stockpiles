"""Background worker that scans an image locally and routes it to outputs.

Two sources are supported: a screenshot file selected by the user, or a live
capture of the Foxhole window. Either way the OCR runs in-process via
:class:`LocalScanService` and the result is dispatched to the configured output
handlers, off the GUI thread.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.capture import capture_window
from foxhole_stockpiles.services.local_scan import LocalScanService


class LocalScanWorker(QThread):
    """Scan a file or a live capture and emit the resulting stockpile.

    The completion signal is named ``scan_finished`` (not ``finished``) to avoid
    shadowing ``QThread``'s built-in ``finished`` signal.
    """

    scan_finished = Signal(object)  # Stockpile
    scan_error = Signal(str)

    def __init__(
        self,
        service: LocalScanService,
        *,
        filepath: str | None = None,
        capture: bool = False,
    ) -> None:
        """Initialize the worker.

        Provide ``filepath`` to scan a file, or set ``capture`` to grab the live
        Foxhole window.

        Args:
            service (LocalScanService): The in-process scan service.
            filepath (str | None): Path to a screenshot file to scan.
            capture (bool): Capture the Foxhole window instead of reading a file.
        """
        super().__init__()
        self._service = service
        self._filepath = filepath
        self._capture = capture

    def run(self) -> None:
        """Run the scan in the background thread."""
        try:
            if self._filepath is not None:
                stockpile: Stockpile = self._service.scan(self._filepath)
            elif self._capture:
                image = capture_window()
                stockpile = self._service.scan(image)
            else:  # pragma: no cover - guarded by the caller
                raise ValueError("Either filepath or capture must be provided")
            self.scan_finished.emit(stockpile)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.scan_error.emit(str(exc))
