"""SAV file input method: one-shot scans and file monitoring."""

import logging
from enum import StrEnum
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.utils import auto_detect_savefile
from foxhole_stockpiles.enums.sav_mode import SavMode
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
        super().__init__(host=host, parent=parent, manual_mode=SavMode.MANUAL)

    def _read_mode(self) -> StrEnum:
        """Read the configured SAV mode from settings.

        Returns:
            StrEnum: The configured mode.
        """
        return AppSettings().sav_processing.mode

    def _validate_config(self) -> tuple[Path | None, str | None]:
        """Validate SAV processing configuration.

        Returns:
            tuple[Path | None, str | None]: The (sav_path, error_message) pair.
                If error_message is not None, the sav_path is invalid.
        """
        try:
            settings = AppSettings()
        except Exception as e:  # noqa: BLE001 - surface config errors to the user
            return None, t("server_panel.sav.error_loading_settings", error=str(e))

        sav_path = settings.sav_processing.sav_file_path
        if not sav_path:
            sav_path = auto_detect_savefile()

        if not sav_path:
            return None, t("server_panel.sav.error_no_sav_file")

        if not sav_path.exists():
            return None, t("server_panel.sav.error_sav_not_found")

        return sav_path, None

    def scan_from_menu(self) -> None:
        """Scan the configured .sav file once (called from the File menu)."""
        sav_path, error = self._validate_config()
        if error:
            QMessageBox.warning(self._parent, t("server_panel.sav.error_title"), error)
            return
        self._run_scan(sav_path)

    def on_capture_triggered(self) -> None:
        """Scan the .sav file once when the SAV hotkey is pressed (GUI thread)."""
        sav_path, error = self._validate_config()
        if error:
            logger.error("[SAV] %s", error)
            return
        self._run_scan(sav_path)

    def _run_scan(self, sav_path: Path | None) -> None:
        """Start a one-shot SAV scan worker for the given path.

        Args:
            sav_path (Path | None): Validated path to the .sav file to scan.
        """
        if self._scan_running():
            logger.warning("SAV scan already in progress")
            return

        try:
            output_coordinator = OutputCoordinator(AppSettings().output)
        except Exception as e:  # noqa: BLE001 - surface config/output errors in the log
            logger.error("[SAV] %s", t("server_panel.sav.error_output", error=str(e)))
            return

        assert sav_path is not None

        logger.info("Starting SAV scan: %s", sav_path)
        worker = SavScanWorker(sav_path=sav_path, output_coordinator=output_coordinator)
        worker.stockpiles_found.connect(self._on_stockpiles)
        self._launch_scan(worker)

    def start_monitor(self) -> None:
        """Start auto-polling the configured .sav file for changes."""
        if self._monitor_running():
            logger.warning("Cannot start monitor: previous monitor still stopping")
            return

        sav_path, error = self._validate_config()
        if error:
            QMessageBox.warning(self._parent, t("server_panel.sav.error_title"), error)
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

        assert sav_path is not None

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
