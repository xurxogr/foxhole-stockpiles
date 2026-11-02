"""Clipboard input method: one-shot reads and clipboard monitoring."""

import logging
from enum import StrEnum

from PySide6.QtWidgets import QMessageBox, QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.enums.clip_mode import ClipMode
from foxhole_stockpiles.gui.controllers.monitor_pipeline import MonitorPipeline
from foxhole_stockpiles.gui.controllers.pipeline_host import PipelineHost
from foxhole_stockpiles.gui.utils.capture_feed_formatting import stockpile_summary
from foxhole_stockpiles.gui.utils.clipboard_monitor_worker import ClipboardMonitorWorker
from foxhole_stockpiles.gui.utils.clipboard_scan_worker import ClipboardScanWorker
from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.clipboard_scan import (
    ClipboardScanService,
    build_clipboard_scan_service,
)

logger = logging.getLogger(__name__)


class ClipPipeline(MonitorPipeline):
    """Read the clipboard on a hotkey, or monitor it for new stockpile exports."""

    _log_tag = "Clipboard"
    _monitor_name = "clipboard"
    _armed_key = "activity.clip_capture_started"
    _disarmed_key = "activity.clip_capture_stopped"
    _monitor_started_key = "activity.clip_monitor_started"
    _monitor_stopped_key = "activity.clip_monitor_stopped"
    _error_key = "activity.clip_error"

    def __init__(self, host: PipelineHost, parent: QWidget) -> None:
        """Initialize the clipboard pipeline.

        Args:
            host (PipelineHost): The widget this pipeline reports to.
            parent (QWidget): Owner of this pipeline and parent of its dialogs.
        """
        super().__init__(host=host, parent=parent, manual_mode=ClipMode.MANUAL)
        self._service: ClipboardScanService | None = None

    def _read_mode(self) -> StrEnum:
        """Read the configured clipboard mode from settings.

        Returns:
            StrEnum: The configured mode.
        """
        return AppSettings().clipboard.mode

    def reset_service(self) -> None:
        """Drop the cached service so it is rebuilt from the current settings."""
        self._service = None

    def _get_service(self) -> ClipboardScanService | None:
        """Build (once) and return the clipboard scan service.

        Returns:
            ClipboardScanService | None: The service, or None if it could not be
                built (e.g. catalog missing); an error is logged in that case.
        """
        if self._service is not None:
            return self._service

        try:
            self._service = build_clipboard_scan_service(AppSettings())
        except Exception as e:  # noqa: BLE001 - surface config/catalog errors in the log
            logger.error("Cannot initialize clipboard scanner: %s", e)
            return None
        return self._service

    def on_capture_triggered(self) -> None:
        """Read and scan the clipboard once when the hotkey fires (GUI thread)."""
        if self._scan_running():
            logger.debug("Clipboard scan already in progress; ignoring hotkey")
            return

        service = self._get_service()
        if service is None:
            return

        worker = ClipboardScanWorker(service)
        worker.stockpile_found.connect(self._on_stockpile_found)
        self._launch_scan(worker)

    def start_monitor(self) -> None:
        """Start auto-polling the clipboard for new stockpile exports."""
        if self._monitor_running():
            logger.warning("Cannot start monitor: previous clipboard monitor still stopping")
            return

        service = self._get_service()
        if service is None:
            QMessageBox.warning(
                self._parent,
                t("server_panel.clip.error_title"),
                t("server_panel.clip.error_no_catalog"),
            )
            return

        try:
            poll_interval = AppSettings().clipboard.poll_interval
        except Exception as e:  # noqa: BLE001 - surface config errors to the user
            QMessageBox.critical(self._parent, t("server_panel.clip.error_title"), str(e))
            return

        # Treat whatever is already on the clipboard as "seen" so only a new
        # export triggers an emit.
        service.prime()

        logger.info("Starting clipboard monitor (poll: %ss)", poll_interval)
        self._mark_monitoring()

        worker = ClipboardMonitorWorker(service=service, poll_interval=poll_interval)
        worker.stockpile_found.connect(self._on_stockpile_found)
        self._launch_monitor(worker)

    def _on_stockpile_found(self, stockpile: Stockpile | None) -> None:
        """Log a short summary when a clipboard scan yields a stockpile.

        Args:
            stockpile (Stockpile | None): The parsed stockpile, or None if the
                clipboard did not hold a recognized stockpile export.
        """
        if stockpile is None:
            logger.info("No stockpile data found in clipboard")
            self._host.feed(t("activity.clip_empty"))
            return
        logger.info(
            "Clipboard scan complete: %d item(s) (%s)",
            len(stockpile.items),
            stockpile.type,
        )
        self._host.feed(t("activity.clip_result", line=stockpile_summary(stockpile)))
