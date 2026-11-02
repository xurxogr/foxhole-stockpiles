"""Screenshot input method: scan a live capture or a file locally."""

import logging

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.gui.controllers.monitor_pipeline import WORKER_WAIT_MS
from foxhole_stockpiles.gui.controllers.pipeline_host import PipelineHost
from foxhole_stockpiles.gui.utils.capture_feed_formatting import ocr_summary
from foxhole_stockpiles.gui.utils.capture_scan_worker import LocalScanWorker
from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.local_scan import LocalScanService

logger = logging.getLogger(__name__)


class OcrPipeline(QObject):
    """Capture the Foxhole window or read a file, and scan it in-process."""

    def __init__(self, host: PipelineHost, parent: QWidget) -> None:
        """Initialize the OCR pipeline.

        Args:
            host (PipelineHost): The widget this pipeline reports to.
            parent (QWidget): Owner of this pipeline and parent of its dialogs.
        """
        super().__init__(parent)
        self._host = host
        self._parent = parent
        self._service: LocalScanService | None = None
        self._capture_busy = False
        self._workers: list[LocalScanWorker] = []

    def reset_service(self) -> None:
        """Drop the cached service so it is rebuilt from the current settings."""
        self._service = None

    def shutdown(self) -> None:
        """Wait for the running scans to finish."""
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(WORKER_WAIT_MS)

    def _get_service(self) -> LocalScanService | None:
        """Build (once) and return the local scan service.

        Returns:
            LocalScanService | None: The scan service, or None if it could not be
                built (e.g. database missing); an error is logged in that case.
        """
        if self._service is not None:
            return self._service

        try:
            self._service = LocalScanService(AppSettings())
        except Exception as e:  # noqa: BLE001 - surface config/DB errors in the log
            logger.error("Cannot initialize scanner: %s", e)
            return None
        return self._service

    def on_capture_triggered(self) -> None:
        """Capture the Foxhole window and scan it (runs on the GUI thread)."""
        if self._capture_busy:
            logger.debug("Capture already in progress; ignoring hotkey")
            return

        service = self._get_service()
        if service is None:
            return

        settings = AppSettings()
        self._capture_busy = True
        worker = LocalScanWorker(
            service,
            capture=True,
            screenshots_folder=settings.scanner.screenshots_folder,
        )
        self._start_worker(worker=worker, mark_capture=True)

    def scan_screenshot_from_menu(self) -> None:
        """Open a file dialog to select and scan a screenshot (called from menu)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self._parent,
            t("server_panel.select_screenshot"),
            "",
            t("common.image_filter"),
        )
        if filepath:
            self.process_screenshot(filepath)

    def process_screenshot(self, filepath: str) -> None:
        """Scan a screenshot file locally.

        Args:
            filepath (str): Path to the screenshot file.
        """
        service = self._get_service()
        if service is None:
            logger.error(t("server_panel.errors.cannot_scan"))
            return

        worker = LocalScanWorker(service, filepath=filepath)
        self._start_worker(worker=worker, mark_capture=False)

    def _start_worker(self, worker: LocalScanWorker, *, mark_capture: bool) -> None:
        """Wire up and start a scan worker, keeping a reference until it finishes.

        Args:
            worker (LocalScanWorker): The worker to start.
            mark_capture (bool): Whether this worker was started by the hotkey
                (so the busy flag is cleared when it finishes).
        """
        worker.scan_finished.connect(self._on_scan_finished)
        worker.output_response.connect(self._host.on_output_response)
        worker.scan_error.connect(self._on_scan_error)

        def _done() -> None:
            if mark_capture:
                self._capture_busy = False
            if worker in self._workers:
                self._workers.remove(worker)

        worker.scan_finished.connect(lambda _stockpile: _done())
        worker.scan_error.connect(lambda _msg: _done())
        self._workers.append(worker)
        worker.start()

    def _on_scan_finished(self, stockpile: Stockpile) -> None:
        """Log a short summary when a scan completes.

        Args:
            stockpile (Stockpile): The detected stockpile.
        """
        logger.info(
            "Scan complete: %d item(s) detected (%s)",
            len(stockpile.items),
            stockpile.type,
        )
        self._host.feed(t("activity.ocr_result", line=ocr_summary(stockpile)))

    def _on_scan_error(self, message: str) -> None:
        """Log a scan failure.

        Args:
            message (str): The error message.
        """
        logger.error("Scan failed: %s", message)
        self._host.feed(t("activity.scan_error", error=message))
