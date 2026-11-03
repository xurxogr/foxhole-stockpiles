"""SAV file input method: one-shot scans and file monitoring."""

import logging
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.utils import auto_detect_savefile
from foxhole_stockpiles.enums.capture_mode import CaptureMode
from foxhole_stockpiles.gui.controllers.monitor_pipeline import MonitorPipeline
from foxhole_stockpiles.gui.controllers.pipeline_host import PipelineHost
from foxhole_stockpiles.gui.utils.capture_feed_formatting import stockpile_summary
from foxhole_stockpiles.gui.utils.sav_monitor_worker import SavMonitorWorker
from foxhole_stockpiles.gui.utils.sav_scan_worker import SavScanWorker
from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator

logger = logging.getLogger(__name__)


class SavPipeline(MonitorPipeline):
    """Scan the .sav file on a hotkey or the menu, or monitor it for changes."""

    _log_tag = "SAV"
    _monitor_name = "SAV"
    _armed_key = "activity.sav_capture_started"
    _disarmed_key = "activity.sav_capture_stopped"
    _monitor_started_key = "activity.sav_monitor_started"
    _monitor_stopped_key = "activity.sav_monitor_stopped"
    _error_key = "activity.sav_error"

    def __init__(self, host: PipelineHost, parent: QWidget) -> None:
        """Initialize the SAV pipeline.

        Args:
            host (PipelineHost): The widget this pipeline reports to.
            parent (QWidget): Owner of this pipeline and parent of its dialogs.
        """
        super().__init__(host=host, parent=parent)

    def _read_mode(self) -> CaptureMode:
        """Read the configured SAV mode from settings.

        Returns:
            CaptureMode: The configured mode.
        """
        return AppSettings().sav_processing.mode

    def _configured_sav_path(self) -> Path:
        """Find the .sav file to process.

        Returns:
            Path: The configured or auto-detected file, which exists.

        Raises:
            ValueError: If there is none, with the message to show to the user.
        """
        try:
            settings = AppSettings()
        except Exception as e:  # noqa: BLE001 - surface config errors to the user
            raise ValueError(t("server_panel.sav.error_loading_settings", error=str(e))) from e

        sav_path = settings.sav_processing.sav_file_path or auto_detect_savefile()
        if not sav_path:
            raise ValueError(t("server_panel.sav.error_no_sav_file"))
        if not sav_path.exists():
            raise ValueError(t("server_panel.sav.error_sav_not_found"))
        return sav_path

    def scan_from_menu(self) -> None:
        """Scan the configured .sav file once (called from the File menu)."""
        try:
            sav_path = self._configured_sav_path()
        except ValueError as e:
            QMessageBox.warning(self._parent, t("server_panel.sav.error_title"), str(e))
            return
        self._run_scan(sav_path)

    def on_capture_triggered(self) -> None:
        """Scan the .sav file once when the SAV hotkey is pressed (GUI thread)."""
        try:
            sav_path = self._configured_sav_path()
        except ValueError as e:
            logger.error("[SAV] %s", e)
            return
        self._run_scan(sav_path)

    def _run_scan(self, sav_path: Path) -> None:
        """Start a one-shot SAV scan worker for the given path.

        Args:
            sav_path (Path): Validated path to the .sav file to scan.
        """
        if self._scan_running():
            logger.warning("SAV scan already in progress")
            return

        try:
            output_coordinator = OutputCoordinator(AppSettings().output)
        except Exception as e:  # noqa: BLE001 - surface config/output errors in the log
            logger.error("[SAV] %s", t("server_panel.sav.error_output", error=str(e)))
            return

        logger.info("Starting SAV scan: %s", sav_path)
        worker = SavScanWorker(sav_path=sav_path, output_coordinator=output_coordinator)
        worker.stockpiles_found.connect(self._on_stockpiles)
        self._launch_scan(worker)

    def start_monitor(self) -> None:
        """Start auto-polling the configured .sav file for changes."""
        if self._monitor_running():
            logger.warning("Cannot start monitor: previous monitor still stopping")
            return

        try:
            sav_path = self._configured_sav_path()
        except ValueError as e:
            QMessageBox.warning(self._parent, t("server_panel.sav.error_title"), str(e))
            return

        try:
            settings = AppSettings()
            output_coordinator = OutputCoordinator(settings.output)
            poll_interval = settings.sav_processing.poll_interval
        except Exception as e:  # noqa: BLE001 - surface config/output errors to the user
            QMessageBox.critical(
                self._parent,
                t("server_panel.sav.error_title"),
                t("server_panel.sav.error_output", error=str(e)),
            )
            return

        logger.info("Starting SAV monitor: %s (poll: %ss)", sav_path, poll_interval)
        self._mark_monitoring()

        worker = SavMonitorWorker(
            sav_path=sav_path,
            output_coordinator=output_coordinator,
            poll_interval=poll_interval,
        )
        worker.stockpiles_changed.connect(self._on_stockpiles)
        self._launch_monitor(worker)

    def _on_stockpiles(self, stockpiles: list[Stockpile]) -> None:
        """Show a SAV scan summary plus one feed line per scanned structure.

        Args:
            stockpiles (list[Stockpile]): The structures scanned (or changed).
        """
        if not stockpiles:
            return
        self._host.feed(t("activity.sav_summary", count=len(stockpiles)))
        for stockpile in stockpiles:
            self._host.feed_detail(stockpile_summary(stockpile))
