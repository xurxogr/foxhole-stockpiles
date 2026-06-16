"""Server control panel widget for managing the FastAPI server and scanning screenshots."""

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

from foxhole_stockpiles.api.dependencies import clear_dependency_caches
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.utils import auto_detect_savefile
from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler
from foxhole_stockpiles.gui.utils.sav_workers import SavMonitorWorker, SavScanWorker
from foxhole_stockpiles.gui.utils.scan_worker import ScanWorker
from foxhole_stockpiles.gui.utils.scanner_client import ScannerClient
from foxhole_stockpiles.gui.utils.server_thread import ServerThread
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator

logger = logging.getLogger(__name__)


class ServerControlPanel(QWidget):
    """Panel for controlling the FastAPI server and scanning screenshots."""

    server_started = Signal()
    server_stopped = Signal()
    screenshot_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the server control panel.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.server_running = False
        self.server_thread: ServerThread | None = None

        # SAV processing state
        self._sav_scan_worker: SavScanWorker | None = None
        self._sav_monitor_worker: SavMonitorWorker | None = None
        self._sav_monitoring = False

        # Setup log handler and attach to root logger immediately
        # This allows capturing logs even before the server starts
        self.log_handler = QtLogHandler()
        self.log_handler.log_message.connect(self.append_log)
        self._attach_log_handler()

        # Setup scanner client
        self.scanner_client = ScannerClient()

        self.init_ui()

        # Connect to language changes with cleanup on destruction
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(self._cleanup)

    def _cleanup(self) -> None:
        """Clean up resources when widget is destroyed."""
        off_language_changed(self._language_callback)
        self._stop_all_workers()

    def _stop_all_workers(self) -> None:
        """Stop all running worker threads and wait for them to finish."""
        # Stop SAV monitor worker
        if self._sav_monitor_worker and self._sav_monitor_worker.isRunning():
            self._sav_monitor_worker.stop()
            self._sav_monitor_worker.wait(2000)  # Wait up to 2 seconds

        # Stop SAV scan worker (can't really stop it, just wait)
        if self._sav_scan_worker and self._sav_scan_worker.isRunning():
            self._sav_scan_worker.wait(2000)  # Wait up to 2 seconds

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event.

        Args:
            _language: The new language code (unused).
        """
        self.retranslate()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Top section: two columns (SAV Processing | Server)
        top_layout = QHBoxLayout()

        # === Left side: SAV Processing ===
        self.sav_group = QGroupBox("")
        sav_layout = QVBoxLayout(self.sav_group)

        # SAV buttons row
        sav_buttons_layout = QHBoxLayout()
        self.scan_sav_button = QPushButton("")
        self.scan_sav_button.clicked.connect(self.scan_sav_file)
        sav_buttons_layout.addWidget(self.scan_sav_button)

        self.monitor_sav_button = QPushButton("")
        self.monitor_sav_button.clicked.connect(self.toggle_sav_monitor)
        sav_buttons_layout.addWidget(self.monitor_sav_button)

        sav_buttons_layout.addStretch()
        sav_layout.addLayout(sav_buttons_layout)

        # SAV status
        self.sav_status_label = QLabel("")
        self.sav_status_label.setStyleSheet("QLabel { font-size: 11px; color: #888; }")
        sav_layout.addWidget(self.sav_status_label)

        top_layout.addWidget(self.sav_group, 1)

        # === Right side: Server ===
        self.server_group = QGroupBox("")
        server_layout = QVBoxLayout(self.server_group)

        # Server button and status row
        server_control_layout = QHBoxLayout()
        self.start_stop_button = QPushButton("Start Server")
        self.start_stop_button.clicked.connect(self.toggle_server)
        server_control_layout.addWidget(self.start_stop_button)

        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("QLabel { font-weight: bold; }")
        server_control_layout.addWidget(self.status_label)

        server_control_layout.addStretch()
        server_layout.addLayout(server_control_layout)

        # DB info label
        self.db_info_text = QLabel("")
        self.db_info_text.setStyleSheet("QLabel { font-size: 11px; color: #888; }")
        server_layout.addWidget(self.db_info_text)

        top_layout.addWidget(self.server_group, 1)

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

        # Server Logs Group (shown when everything valid)
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

        # Set column widths
        header = self.log_display.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        # Set minimum column widths
        self.log_display.setColumnWidth(0, 150)  # Time
        self.log_display.setColumnWidth(1, 80)  # Level
        self.log_display.setColumnWidth(2, 250)  # Module

        logs_layout.addWidget(self.log_display)

        # Log controls
        log_controls = QHBoxLayout()
        self.clear_logs_button = QPushButton("")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        log_controls.addStretch()
        log_controls.addWidget(self.clear_logs_button)
        logs_layout.addLayout(log_controls)

        layout.addWidget(self.logs_group)

        # Apply initial translations
        self.retranslate()

        # Initial validation
        self._update_validation_state()

    def refresh_db_info(self) -> None:
        """Refresh the database info and validation state."""
        self._update_validation_state()

    def on_database_updated(self, updated_db_path: Path) -> None:
        """Handle database file being updated.

        Called when the database builder successfully updates a database file.
        If the updated file matches the configured database, refresh the info
        and restart the server to pick up the changes.

        Args:
            updated_db_path: Path to the database file that was updated
        """
        # Check if the updated database is the one we're using
        try:
            settings = AppSettings()
            configured_path = settings.scanner.database_path
            if configured_path is None:
                return

            # Resolve both paths for comparison
            configured_resolved = Path(configured_path).resolve()
            updated_resolved = Path(updated_db_path).resolve()

            if configured_resolved != updated_resolved:
                return

            logger.info("Configured database was updated")

            # Refresh the database info display
            self._update_validation_state()

            # Restart server to pick up the new database
            if self.server_running:
                logger.info("Restarting server to load updated database...")
                self.stop_server()
                self.start_server()

        except Exception as e:
            logger.warning("Error checking database update: %s", e)

    def _update_validation_state(self) -> None:
        """Update the validation state and show/hide appropriate panels."""
        is_valid = False
        error_message = ""
        db_info = ""

        try:
            # Try to load config
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
                # The database file is present. FS does not read the template
                # DB format (only fs-tools and fs-ocr do), so validity here is
                # simply "configured and present"; mods are not introspected.
                db_path_obj = Path(db_path)
                try:
                    # Try to get relative path from current working directory
                    rel_path = db_path_obj.relative_to(Path.cwd())
                    display_path = str(rel_path)
                except ValueError:
                    # Path is not relative to cwd, just show filename
                    display_path = db_path_obj.name

                is_valid = True
                db_info = f"Database: {display_path}"

        except (ValidationError, OSError, ValueError):
            # ValidationError: invalid config values
            # OSError: config file read error
            # ValueError: JSON decode error or invalid data
            error_message = (
                f"<b>⚙️ {t('server_panel.errors.no_config_title')}</b><br><br>"
                f"{t('server_panel.errors.no_config_message')}"
            )

        # Update UI based on validation state
        if is_valid:
            # Show DB info and logs, hide error panel
            self.db_info_text.setText(db_info)
            self.db_info_text.setVisible(True)
            self.error_panel.setVisible(False)
            self.logs_group.setVisible(True)
            self.start_stop_button.setEnabled(True)
        else:
            # Show error panel, hide DB info and logs
            self.error_panel.setText(error_message)
            self.error_panel.setVisible(True)
            self.db_info_text.setVisible(False)
            self.logs_group.setVisible(False)
            self.start_stop_button.setEnabled(False)

    def scan_screenshot_from_menu(self) -> None:
        """Open file dialog to select and scan a screenshot (called from menu)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            t("server_panel.select_screenshot"),
            "",
            t("common.image_filter"),
        )
        if filepath:
            self.process_screenshot(filepath)

    def toggle_server(self) -> None:
        """Toggle server start/stop."""
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()

    def _attach_log_handler(self) -> None:
        """Attach the Qt log handler to root logger if not already attached."""
        root_logger = logging.getLogger()

        # Check if our handler is already attached (by name)
        for handler in root_logger.handlers:
            if getattr(handler, "name", None) == QtLogHandler.HANDLER_NAME:
                return  # Already attached

        root_logger.addHandler(self.log_handler)

    def start_server(self) -> None:
        """Start the FastAPI server."""
        logger.info("Starting server...")

        # Create and start server thread
        self.server_thread = ServerThread()
        self.server_thread.start()

        self.server_running = True
        self.start_stop_button.setText(t("server_panel.stop_server"))
        self.status_label.setText(t("server_panel.status_running"))
        self.status_label.setStyleSheet("QLabel { font-weight: bold; color: green; }")
        self.server_started.emit()

    def stop_server(self) -> None:
        """Stop the FastAPI server."""
        logger.info("Stopping server...")

        # Stop server thread and wait for it to finish (allows lifespan cleanup)
        if self.server_thread:
            self.server_thread.stop()
            # Wait for server to finish shutdown (including sending notifications)
            self.server_thread.join(timeout=5.0)
            self.server_thread = None

        # Clear all dependency caches so next start picks up fresh settings
        clear_dependency_caches()

        # Note: Keep the log handler attached so we continue to see logs
        # even when the server is stopped

        self.server_running = False
        self.start_stop_button.setText(t("server_panel.start_server"))
        self.status_label.setText(t("server_panel.status_stopped"))
        self.status_label.setStyleSheet("QLabel { font-weight: bold; color: red; }")
        self.server_stopped.emit()

    def process_screenshot(self, filepath: str) -> None:
        """Process a screenshot file.

        Args:
            filepath (str): Path to the screenshot file
        """
        # Check if server is running
        if not self.server_running:
            logger.error(t("server_panel.errors.cannot_scan"))
            return

        # Scan the screenshot in background thread
        worker = ScanWorker(self.scanner_client, filepath)
        worker.finished.connect(lambda: self.screenshot_dropped.emit(filepath))
        worker.start()

        # Keep reference to prevent garbage collection
        if not hasattr(self, "_scan_workers"):
            self._scan_workers = []
        self._scan_workers.append(worker)
        worker.finished.connect(lambda: self._scan_workers.remove(worker))

    def append_log(self, log_data: dict[str, str]) -> None:
        """Append a log entry to the log display.

        Args:
            log_data (dict[str, str]): Dictionary containing timestamp, level, module, message,
                and color
        """
        row_position = self.log_display.rowCount()
        self.log_display.insertRow(row_position)

        color = QColor(log_data["color"])
        brush = QBrush(color)

        # Create table items
        time_item = QTableWidgetItem(log_data["timestamp"])
        time_item.setForeground(brush)

        level_item = QTableWidgetItem(log_data["level"])
        level_item.setForeground(brush)

        module_item = QTableWidgetItem(log_data["module"])
        module_item.setForeground(brush)

        message_item = QTableWidgetItem(log_data["message"])
        message_item.setForeground(brush)

        # Add items to table
        self.log_display.setItem(row_position, 0, time_item)
        self.log_display.setItem(row_position, 1, level_item)
        self.log_display.setItem(row_position, 2, module_item)
        self.log_display.setItem(row_position, 3, message_item)

        # Auto-scroll to bottom
        self.log_display.scrollToBottom()

    def clear_logs(self) -> None:
        """Clear the log display."""
        self.log_display.setRowCount(0)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        # Group titles
        self.sav_group.setTitle(t("server_panel.sav_group_title"))
        self.server_group.setTitle(t("server_panel.server_group_title"))

        # Button text depends on server state
        if self.server_running:
            self.start_stop_button.setText(t("server_panel.stop_server"))
            self.status_label.setText(t("server_panel.status_running"))
        else:
            self.start_stop_button.setText(t("server_panel.start_server"))
            self.status_label.setText(t("server_panel.status_stopped"))

        # Log table headers
        self.log_display.setHorizontalHeaderLabels(
            [
                t("common.log_columns.time"),
                t("common.log_columns.level"),
                t("common.log_columns.module"),
                t("common.log_columns.message"),
            ]
        )

        # Clear logs button
        self.clear_logs_button.setText(t("common.clear_logs"))

        # SAV processing buttons
        self.scan_sav_button.setText(t("server_panel.scan_sav"))
        if self._sav_monitoring:
            self.monitor_sav_button.setText(t("server_panel.stop_monitor"))
        else:
            self.monitor_sav_button.setText(t("server_panel.start_monitor"))

    # ==================== SAV Processing ====================

    def _validate_sav_config(self) -> tuple[Path | None, str | None]:
        """Validate SAV processing configuration.

        Returns:
            tuple: (sav_path, error_message)
                   If error_message is not None, the sav_path is invalid.
        """
        try:
            settings = AppSettings()
        except Exception as e:
            return None, t("server_panel.sav.error_loading_settings", error=str(e))

        # Check SAV file path
        sav_path = settings.sav_processing.sav_file_path
        if not sav_path:
            # Try auto-detect
            sav_path = auto_detect_savefile()

        if not sav_path:
            return None, t("server_panel.sav.error_no_sav_file")

        if not sav_path.exists():
            return None, t("server_panel.sav.error_sav_not_found")

        return sav_path, None

    def scan_sav_file(self) -> None:
        """Perform a one-time SAV file scan."""
        # Validate configuration
        sav_path, error = self._validate_sav_config()
        if error:
            QMessageBox.warning(
                self,
                t("server_panel.sav.error_title"),
                error,
            )
            return

        # Don't start if already scanning
        if self._sav_scan_worker and self._sav_scan_worker.isRunning():
            logger.warning("SAV scan already in progress")
            return

        # Create output coordinator
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

        # At this point validation passed, so path is guaranteed to be non-None
        assert sav_path is not None

        logger.info(f"Starting SAV scan: {sav_path}")
        self.sav_status_label.setText(t("server_panel.sav.status_scanning"))
        self.sav_status_label.setStyleSheet("QLabel { font-size: 11px; color: #2196F3; }")
        self.scan_sav_button.setEnabled(False)

        # Create and start worker
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
        # Don't start if previous monitor is still running
        if self._sav_monitor_worker and self._sav_monitor_worker.isRunning():
            logger.warning("Cannot start monitor: previous monitor still stopping")
            return

        # Validate configuration
        sav_path, error = self._validate_sav_config()
        if error:
            QMessageBox.warning(
                self,
                t("server_panel.sav.error_title"),
                error,
            )
            return

        # Create output coordinator
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

        # At this point validation passed, so path is guaranteed to be non-None
        assert sav_path is not None

        logger.info(f"Starting SAV monitor: {sav_path} (poll: {poll_interval}s)")
        self._sav_monitoring = True
        self.monitor_sav_button.setText(t("server_panel.stop_monitor"))
        self.sav_status_label.setText(t("server_panel.sav.status_monitoring"))
        self.sav_status_label.setStyleSheet("QLabel { font-size: 11px; color: #4CAF50; }")

        # Create and start worker
        self._sav_monitor_worker = SavMonitorWorker(sav_path, output_coordinator, poll_interval)
        self._sav_monitor_worker.error.connect(self._on_sav_error)
        self._sav_monitor_worker.finished.connect(self._on_sav_monitor_finished)
        self._sav_monitor_worker.start()

    def _stop_sav_monitor(self) -> None:
        """Stop SAV file monitoring."""
        if self._sav_monitor_worker:
            logger.info("Stopping SAV monitor...")
            self._sav_monitor_worker.stop()

            # Update UI immediately - don't wait for worker to finish
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
        # Only update UI if we're not already in a new monitoring session
        # (user might have started a new monitor before the old one finished)
        sender = self.sender()
        if sender is self._sav_monitor_worker:
            self._sav_monitoring = False
            self.monitor_sav_button.setText(t("server_panel.start_monitor"))
            self.sav_status_label.setText("")
            self._sav_monitor_worker = None
