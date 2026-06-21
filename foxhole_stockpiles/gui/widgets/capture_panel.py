"""Capture control panel: screenshot capture + local scanning, plus SAV tools.

Replaces the former server control panel. Instead of starting a REST server, the
panel runs the OCR engine in-process: a global hotkey (or the *Scan a file* menu
action) captures the Foxhole window, scans it locally, and routes the result to
the configured output handlers.
"""

import logging
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.utils import auto_detect_savefile
from foxhole_stockpiles.gui.utils.capture_scan_worker import LocalScanWorker
from foxhole_stockpiles.gui.utils.hotkey_listener import HotkeyListener
from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler
from foxhole_stockpiles.gui.utils.sav_workers import SavMonitorWorker, SavScanWorker
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.local_scan import LocalScanService
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator

logger = logging.getLogger(__name__)


class CapturePanel(QWidget):
    """Panel for capturing screenshots, scanning them locally, and SAV tools."""

    capture_triggered = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the capture control panel.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.capturing = False
        self._hotkey_listener: HotkeyListener | None = None
        self._scan_service: LocalScanService | None = None
        self._capture_busy = False
        self._scan_workers: list[LocalScanWorker] = []

        # SAV processing state
        self._sav_scan_worker: SavScanWorker | None = None
        self._sav_monitor_worker: SavMonitorWorker | None = None
        self._sav_monitoring = False

        # Setup log handler and attach to root logger immediately
        self.log_handler = QtLogHandler()
        self.log_handler.log_message.connect(self.append_log)
        self._attach_log_handler()

        self.init_ui()

        # Run the capture-and-scan on the GUI thread when the hotkey fires.
        self.capture_triggered.connect(self._on_capture_triggered)

        # Connect to language changes with cleanup on destruction
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(self._cleanup)

    def _cleanup(self) -> None:
        """Clean up resources when widget is destroyed."""
        off_language_changed(self._language_callback)
        self._stop_all_workers()

    def _stop_all_workers(self) -> None:
        """Stop capture, hotkey listener and SAV workers; wait for completion."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

        for worker in list(self._scan_workers):
            if worker.isRunning():
                worker.wait(2000)

        if self._sav_monitor_worker and self._sav_monitor_worker.isRunning():
            self._sav_monitor_worker.stop()
            self._sav_monitor_worker.wait(2000)

        if self._sav_scan_worker and self._sav_scan_worker.isRunning():
            self._sav_scan_worker.wait(2000)

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event.

        Args:
            _language: The new language code (unused).
        """
        self.retranslate()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Top section: two columns (SAV Processing | Capture)
        top_layout = QHBoxLayout()

        # === Left side: SAV Processing ===
        self.sav_group = QGroupBox("")
        sav_layout = QVBoxLayout(self.sav_group)

        sav_buttons_layout = QHBoxLayout()
        self.scan_sav_button = QPushButton("")
        self.scan_sav_button.clicked.connect(self.scan_sav_file)
        sav_buttons_layout.addWidget(self.scan_sav_button)

        self.monitor_sav_button = QPushButton("")
        self.monitor_sav_button.clicked.connect(self.toggle_sav_monitor)
        sav_buttons_layout.addWidget(self.monitor_sav_button)

        sav_buttons_layout.addStretch()
        sav_layout.addLayout(sav_buttons_layout)

        self.sav_status_label = QLabel("")
        self.sav_status_label.setStyleSheet("QLabel { font-size: 11px; color: #888; }")
        sav_layout.addWidget(self.sav_status_label)

        top_layout.addWidget(self.sav_group, 1)

        # === Right side: Capture ===
        self.capture_group = QGroupBox("")
        capture_layout = QVBoxLayout(self.capture_group)

        capture_control_layout = QHBoxLayout()
        self.start_stop_button = QPushButton("Start Capture")
        self.start_stop_button.clicked.connect(self.toggle_capture)
        capture_control_layout.addWidget(self.start_stop_button)

        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("QLabel { font-weight: bold; }")
        capture_control_layout.addWidget(self.status_label)

        capture_control_layout.addStretch()
        capture_layout.addLayout(capture_control_layout)

        # DB info label
        self.db_info_text = QLabel("")
        self.db_info_text.setStyleSheet("QLabel { font-size: 11px; color: #888; }")
        capture_layout.addWidget(self.db_info_text)

        top_layout.addWidget(self.capture_group, 1)

        layout.addLayout(top_layout)

        # Error panel (shown when config/DB invalid, replaces logs)
        self.error_panel = QLabel("")
        self.error_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_panel.setWordWrap(True)
        self.error_panel.setStyleSheet(
            "QLabel { "
            "border: 2px solid #FF9800; "
            "border-radius: 8px; "
            "background-color: palette(alternate-base); "
            "font-size: 13px; "
            "padding: 15px; "
            "}"
        )
        layout.addWidget(self.error_panel)

        # Logs Group (shown when everything valid)
        self.logs_group = QGroupBox("")
        logs_layout = QVBoxLayout()
        self.logs_group.setLayout(logs_layout)

        self.log_display = QTableWidget()
        self.log_display.setColumnCount(4)
        self.log_display.setHorizontalHeaderLabels(["Time", "Level", "Module", "Message"])
        self.log_display.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_display.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        vertical_header = self.log_display.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)
        self.log_display.setStyleSheet(
            "QTableWidget { background-color: #1E1E1E; gridline-color: #3E3E3E; }"
        )

        header = self.log_display.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.log_display.setColumnWidth(0, 150)
        self.log_display.setColumnWidth(1, 80)
        self.log_display.setColumnWidth(2, 250)

        logs_layout.addWidget(self.log_display)

        log_controls = QHBoxLayout()
        self.clear_logs_button = QPushButton("")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        log_controls.addStretch()
        log_controls.addWidget(self.clear_logs_button)
        logs_layout.addLayout(log_controls)

        layout.addWidget(self.logs_group)

        self.retranslate()
        self._update_validation_state()

    def refresh_db_info(self) -> None:
        """Refresh the database info and validation state (rebuilds the scanner)."""
        # Settings may have changed; drop the cached scan service so it rebuilds.
        self._scan_service = None
        self._update_validation_state()

    def _update_validation_state(self) -> None:
        """Update the validation state and show/hide appropriate panels."""
        is_valid = False
        error_message = ""
        db_info = ""

        try:
            settings = AppSettings()
            db_path = settings.scanner.database_path

            if not db_path:
                error_message = (
                    f"<b>⚙️ {t('server_panel.errors.config_incomplete_title')}</b><br><br>"
                    f"{t('server_panel.errors.config_incomplete_message')}"
                )
            elif not Path(db_path).exists():
                error_message = (
                    f"<b>⚠️ {t('server_panel.errors.database_not_found_title')}</b><br><br>"
                    f"{t('server_panel.errors.database_not_found_message')}"
                )
            else:
                db_path_obj = Path(db_path)
                try:
                    rel_path = db_path_obj.relative_to(Path.cwd())
                    display_path = str(rel_path)
                except ValueError:
                    display_path = db_path_obj.name

                is_valid = True
                db_info = f"Database: {display_path}"

        except (ValidationError, OSError, ValueError):
            error_message = (
                f"<b>⚙️ {t('server_panel.errors.no_config_title')}</b><br><br>"
                f"{t('server_panel.errors.no_config_message')}"
            )

        if is_valid:
            self.db_info_text.setText(db_info)
            self.db_info_text.setVisible(True)
            self.error_panel.setVisible(False)
            self.logs_group.setVisible(True)
            self.start_stop_button.setEnabled(True)
        else:
            self.error_panel.setText(error_message)
            self.error_panel.setVisible(True)
            self.db_info_text.setVisible(False)
            self.logs_group.setVisible(False)
            self.start_stop_button.setEnabled(False)

    def _get_scan_service(self) -> LocalScanService | None:
        """Build (once) and return the local scan service.

        Returns:
            LocalScanService | None: The scan service, or None if it could not be
                built (e.g. database missing); an error is logged in that case.
        """
        if self._scan_service is not None:
            return self._scan_service

        try:
            self._scan_service = LocalScanService(AppSettings())
        except Exception as e:  # noqa: BLE001 - surface config/DB errors in the log
            logger.error("Cannot initialize scanner: %s", e)
            return None
        return self._scan_service

    def _attach_log_handler(self) -> None:
        """Attach the Qt log handler to root logger if not already attached."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if getattr(handler, "name", None) == QtLogHandler.HANDLER_NAME:
                return
        root_logger.addHandler(self.log_handler)

    # ==================== Capture ====================

    def toggle_capture(self) -> None:
        """Toggle screenshot capture on/off."""
        if self.capturing:
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self) -> None:
        """Start listening for the capture hotkey."""
        settings = AppSettings()
        key = settings.scanner.capture_key
        if not key:
            QMessageBox.warning(
                self,
                t("server_panel.capture_group_title"),
                t("server_panel.capture_no_key"),
            )
            return

        # Ensure the scanner can be built before we start listening.
        if self._get_scan_service() is None:
            QMessageBox.warning(
                self,
                t("server_panel.capture_group_title"),
                t("server_panel.errors.cannot_scan"),
            )
            return

        try:
            self._hotkey_listener = HotkeyListener(key, self.capture_triggered.emit)
            self._hotkey_listener.start()
        except (RuntimeError, ValueError) as e:
            logger.error("Could not start capture: %s", e)
            QMessageBox.warning(self, t("server_panel.capture_group_title"), str(e))
            self._hotkey_listener = None
            return

        self.capturing = True
        self.start_stop_button.setText(t("server_panel.stop_capture"))
        self.status_label.setText(t("server_panel.status_capturing"))
        self.status_label.setStyleSheet("QLabel { font-weight: bold; color: green; }")
        logger.info("Capture started (hotkey: %s)", key)

    def stop_capture(self) -> None:
        """Stop listening for the capture hotkey."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

        self.capturing = False
        self.start_stop_button.setText(t("server_panel.start_capture"))
        self.status_label.setText(t("server_panel.status_stopped"))
        self.status_label.setStyleSheet("QLabel { font-weight: bold; color: red; }")
        logger.info("Capture stopped")

    def _on_capture_triggered(self) -> None:
        """Capture the Foxhole window and scan it (runs on the GUI thread)."""
        if self._capture_busy:
            logger.debug("Capture already in progress; ignoring hotkey")
            return

        service = self._get_scan_service()
        if service is None:
            return

        self._capture_busy = True
        worker = LocalScanWorker(service, capture=True)
        self._start_scan_worker(worker, mark_capture=True)

    def scan_screenshot_from_menu(self) -> None:
        """Open a file dialog to select and scan a screenshot (called from menu)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
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
        service = self._get_scan_service()
        if service is None:
            logger.error(t("server_panel.errors.cannot_scan"))
            return

        worker = LocalScanWorker(service, filepath=filepath)
        self._start_scan_worker(worker, mark_capture=False)

    def _start_scan_worker(self, worker: LocalScanWorker, *, mark_capture: bool) -> None:
        """Wire up and start a scan worker, keeping a reference until it finishes.

        Args:
            worker (LocalScanWorker): The worker to start.
            mark_capture (bool): Whether this worker was started by the hotkey
                (so the busy flag is cleared when it finishes).
        """
        worker.scan_finished.connect(self._on_scan_finished)
        worker.scan_error.connect(self._on_scan_error)

        def _done() -> None:
            if mark_capture:
                self._capture_busy = False
            if worker in self._scan_workers:
                self._scan_workers.remove(worker)

        worker.scan_finished.connect(lambda _stockpile: _done())
        worker.scan_error.connect(lambda _msg: _done())
        self._scan_workers.append(worker)
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

    def _on_scan_error(self, message: str) -> None:
        """Log a scan failure.

        Args:
            message (str): The error message.
        """
        logger.error("Scan failed: %s", message)

    def append_log(self, log_data: dict[str, str]) -> None:
        """Append a log entry to the log display.

        Args:
            log_data (dict[str, str]): Dictionary with timestamp, level, module,
                message, and color.
        """
        row_position = self.log_display.rowCount()
        self.log_display.insertRow(row_position)

        color = QColor(log_data["color"])
        brush = QBrush(color)

        time_item = QTableWidgetItem(log_data["timestamp"])
        time_item.setForeground(brush)
        level_item = QTableWidgetItem(log_data["level"])
        level_item.setForeground(brush)
        module_item = QTableWidgetItem(log_data["module"])
        module_item.setForeground(brush)
        message_item = QTableWidgetItem(log_data["message"])
        message_item.setForeground(brush)

        self.log_display.setItem(row_position, 0, time_item)
        self.log_display.setItem(row_position, 1, level_item)
        self.log_display.setItem(row_position, 2, module_item)
        self.log_display.setItem(row_position, 3, message_item)

        self.log_display.scrollToBottom()

    def clear_logs(self) -> None:
        """Clear the log display."""
        self.log_display.setRowCount(0)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.sav_group.setTitle(t("server_panel.sav_group_title"))
        self.capture_group.setTitle(t("server_panel.capture_group_title"))

        if self.capturing:
            self.start_stop_button.setText(t("server_panel.stop_capture"))
            self.status_label.setText(t("server_panel.status_capturing"))
        else:
            self.start_stop_button.setText(t("server_panel.start_capture"))
            self.status_label.setText(t("server_panel.status_stopped"))

        self.log_display.setHorizontalHeaderLabels(
            [
                t("common.log_columns.time"),
                t("common.log_columns.level"),
                t("common.log_columns.module"),
                t("common.log_columns.message"),
            ]
        )

        self.clear_logs_button.setText(t("common.clear_logs"))

        self.scan_sav_button.setText(t("server_panel.scan_sav"))
        if self._sav_monitoring:
            self.monitor_sav_button.setText(t("server_panel.stop_monitor"))
        else:
            self.monitor_sav_button.setText(t("server_panel.start_monitor"))

    # ==================== SAV Processing ====================

    def _validate_sav_config(self) -> tuple[Path | None, str | None]:
        """Validate SAV processing configuration.

        Returns:
            tuple: (sav_path, error_message). If error_message is not None, the
                sav_path is invalid.
        """
        try:
            settings = AppSettings()
        except Exception as e:
            return None, t("server_panel.sav.error_loading_settings", error=str(e))

        sav_path = settings.sav_processing.sav_file_path
        if not sav_path:
            sav_path = auto_detect_savefile()

        if not sav_path:
            return None, t("server_panel.sav.error_no_sav_file")

        if not sav_path.exists():
            return None, t("server_panel.sav.error_sav_not_found")

        return sav_path, None

    def scan_sav_file(self) -> None:
        """Perform a one-time SAV file scan."""
        sav_path, error = self._validate_sav_config()
        if error:
            QMessageBox.warning(self, t("server_panel.sav.error_title"), error)
            return

        if self._sav_scan_worker and self._sav_scan_worker.isRunning():
            logger.warning("SAV scan already in progress")
            return

        try:
            settings = AppSettings()
            output_coordinator = OutputCoordinator(settings.output)
        except Exception as e:
            QMessageBox.critical(
                self,
                t("server_panel.sav.error_title"),
                t("server_panel.sav.error_output", error=str(e)),
            )
            return

        assert sav_path is not None

        logger.info(f"Starting SAV scan: {sav_path}")
        self.sav_status_label.setText(t("server_panel.sav.status_scanning"))
        self.sav_status_label.setStyleSheet("QLabel { font-size: 11px; color: #2196F3; }")
        self.scan_sav_button.setEnabled(False)

        self._sav_scan_worker = SavScanWorker(sav_path, output_coordinator)
        self._sav_scan_worker.error.connect(self._on_sav_error)
        self._sav_scan_worker.finished.connect(self._on_sav_scan_finished)
        self._sav_scan_worker.start()

    def toggle_sav_monitor(self) -> None:
        """Toggle SAV file monitoring on/off."""
        if self._sav_monitoring:
            self._stop_sav_monitor()
        else:
            self._start_sav_monitor()

    def _start_sav_monitor(self) -> None:
        """Start SAV file monitoring."""
        if self._sav_monitor_worker and self._sav_monitor_worker.isRunning():
            logger.warning("Cannot start monitor: previous monitor still stopping")
            return

        sav_path, error = self._validate_sav_config()
        if error:
            QMessageBox.warning(self, t("server_panel.sav.error_title"), error)
            return

        try:
            settings = AppSettings()
            output_coordinator = OutputCoordinator(settings.output)
            poll_interval = settings.sav_processing.poll_interval
        except Exception as e:
            QMessageBox.critical(
                self,
                t("server_panel.sav.error_title"),
                t("server_panel.sav.error_output", error=str(e)),
            )
            return

        assert sav_path is not None

        logger.info(f"Starting SAV monitor: {sav_path} (poll: {poll_interval}s)")
        self._sav_monitoring = True
        self.monitor_sav_button.setText(t("server_panel.stop_monitor"))
        self.sav_status_label.setText(t("server_panel.sav.status_monitoring"))
        self.sav_status_label.setStyleSheet("QLabel { font-size: 11px; color: #4CAF50; }")

        self._sav_monitor_worker = SavMonitorWorker(sav_path, output_coordinator, poll_interval)
        self._sav_monitor_worker.error.connect(self._on_sav_error)
        self._sav_monitor_worker.finished.connect(self._on_sav_monitor_finished)
        self._sav_monitor_worker.start()

    def _stop_sav_monitor(self) -> None:
        """Stop SAV file monitoring."""
        if self._sav_monitor_worker:
            logger.info("Stopping SAV monitor...")
            self._sav_monitor_worker.stop()

            self._sav_monitoring = False
            self.monitor_sav_button.setText(t("server_panel.start_monitor"))
            self.sav_status_label.setText("")

    def _on_sav_error(self, error_msg: str) -> None:
        """Handle SAV processing error.

        Args:
            error_msg (str): Error message.
        """
        logger.error(f"[SAV] {error_msg}")

    def _on_sav_scan_finished(self, success: bool) -> None:
        """Handle SAV scan finished.

        Args:
            success (bool): Whether scan completed successfully.
        """
        self.scan_sav_button.setEnabled(True)
        self.sav_status_label.setText("")
        self._sav_scan_worker = None

    def _on_sav_monitor_finished(self, success: bool) -> None:
        """Handle SAV monitor finished.

        Args:
            success (bool): Whether monitor stopped normally.
        """
        sender = self.sender()
        if sender is self._sav_monitor_worker:
            self._sav_monitoring = False
            self.monitor_sav_button.setText(t("server_panel.start_monitor"))
            self.sav_status_label.setText("")
            self._sav_monitor_worker = None
