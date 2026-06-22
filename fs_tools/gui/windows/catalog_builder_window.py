"""Catalog builder window for building item catalog from PAK files."""

import logging
import os
import platform
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from fs_tools.gui.utils.catalog_builder_worker import CatalogBuilderWorker

logger = logging.getLogger(__name__)


class CatalogBuilderWindow(QMainWindow):
    """Window for building item catalog from PAK files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the catalog builder window.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.build_worker: CatalogBuilderWorker | None = None
        self.pak_file: str | None = None

        # The launcher only enables this window once it is configured, so the
        # full UI is always built. ``is_configured`` is kept for introspection.
        self.settings = get_settings()
        self.is_configured = self._check_configuration()

        # Setup log handler
        self.log_handler = QtLogHandler()
        self.log_handler.log_message.connect(self.append_log)
        log_level = getattr(logging, self.settings.logging.log_level.upper(), logging.INFO)
        self.log_handler.setLevel(log_level)

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setGeometry(100, 100, 800, 600)
        self._cpu_count = os.cpu_count() or 1

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # PAK File Section
        self.pak_group = QGroupBox()
        pak_layout = QVBoxLayout()
        self.pak_group.setLayout(pak_layout)

        # Info text
        self.pak_info = QLabel()
        self.pak_info.setWordWrap(True)
        pak_layout.addWidget(self.pak_info)

        # PAK file path display
        pak_path_layout = QHBoxLayout()
        self.pak_display = QLineEdit()
        self.pak_display.setReadOnly(True)
        pak_path_layout.addWidget(self.pak_display)

        self.pak_browse_button = QPushButton()
        self.pak_browse_button.clicked.connect(self.select_pak_file)
        pak_path_layout.addWidget(self.pak_browse_button)

        pak_layout.addLayout(pak_path_layout)
        layout.addWidget(self.pak_group)

        # Output Section
        self.output_group = QGroupBox()
        output_layout = QVBoxLayout()
        self.output_group.setLayout(output_layout)

        # Output path
        output_path_layout = QHBoxLayout()
        self.catalog_file_label = QLabel()
        output_path_layout.addWidget(self.catalog_file_label)
        self.output_path_input = QLineEdit()
        self.output_path_input.setText("catalog.json")
        output_path_layout.addWidget(self.output_path_input)

        self.output_browse_button = QPushButton()
        self.output_browse_button.clicked.connect(self.select_output_path)
        output_path_layout.addWidget(self.output_browse_button)

        output_layout.addLayout(output_path_layout)

        # Workers
        workers_layout = QHBoxLayout()
        self.workers_label = QLabel()
        workers_layout.addWidget(self.workers_label)
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setMinimum(1)
        self.workers_spinbox.setMaximum(self._cpu_count)
        self.workers_spinbox.setValue(self._cpu_count)
        self.workers_spinbox.setFixedWidth(80)
        workers_layout.addWidget(self.workers_spinbox)
        self.workers_hint = QLabel()
        self.workers_hint.setStyleSheet("color: gray; font-size: 11px;")
        workers_layout.addWidget(self.workers_hint)
        workers_layout.addStretch()

        output_layout.addLayout(workers_layout)
        layout.addWidget(self.output_group)

        # Logs Section
        self.logs_group = QGroupBox()
        logs_layout = QVBoxLayout()
        self.logs_group.setLayout(logs_layout)

        self.log_display = QTableWidget()
        self.log_display.setColumnCount(4)
        self.log_display.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_display.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_display.setWordWrap(True)
        vertical_header = self.log_display.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)
            vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
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

        self.log_display.setColumnWidth(0, 150)
        self.log_display.setColumnWidth(1, 80)
        self.log_display.setColumnWidth(2, 250)

        # Enable copy on CTRL-C
        self.log_display.keyPressEvent = self._log_key_press_event  # type: ignore[method-assign]

        logs_layout.addWidget(self.log_display)
        layout.addWidget(self.logs_group, stretch=1)

        # Action Buttons
        action_buttons_layout = QHBoxLayout()

        self.start_button = QPushButton()
        self.start_button.clicked.connect(self.start_build)
        action_buttons_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.cancel_build)
        self.cancel_button.setEnabled(False)
        action_buttons_layout.addWidget(self.cancel_button)

        action_buttons_layout.addStretch()

        self.clear_logs_button = QPushButton()
        self.clear_logs_button.clicked.connect(self.clear_logs)
        action_buttons_layout.addWidget(self.clear_logs_button)

        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.close)
        action_buttons_layout.addWidget(self.close_button)

        layout.addLayout(action_buttons_layout)

        # Apply translations
        self.retranslate()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("catalog_builder.title"))
        self.pak_group.setTitle(t("catalog_builder.pak_group"))
        self.pak_info.setText(t("catalog_builder.pak_info"))
        self.pak_display.setPlaceholderText(t("catalog_builder.no_pak_selected"))
        self.pak_browse_button.setText(t("common.browse"))
        self.output_group.setTitle(t("catalog_builder.output_group"))
        self.catalog_file_label.setText(t("catalog_builder.catalog_file"))
        self.output_path_input.setPlaceholderText(t("catalog_builder.catalog_placeholder"))
        self.output_browse_button.setText(t("common.browse"))
        self.workers_label.setText(t("catalog_builder.workers"))
        self.workers_spinbox.setToolTip(t("catalog_builder.workers_tooltip"))
        self.workers_hint.setText(
            t("catalog_builder.cores_detected").replace("{cores}", str(self._cpu_count))
        )
        self.logs_group.setTitle(t("catalog_builder.process_logs"))
        self.log_display.setHorizontalHeaderLabels(
            [
                t("common.log_columns.time"),
                t("common.log_columns.level"),
                t("common.log_columns.module"),
                t("common.log_columns.message"),
            ]
        )
        self.start_button.setText(t("catalog_builder.build_catalog"))
        self.cancel_button.setText(t("common.cancel"))
        self.clear_logs_button.setText(t("common.clear_logs"))
        self.close_button.setText(t("common.close"))

    @staticmethod
    def requirements_met(settings: AppSettings) -> bool:
        """Return whether the catalog builder has everything it needs.

        Args:
            settings (AppSettings): The settings to check.

        Returns:
            bool: True if repak and uassetgui are both configured and exist on
                disk, False otherwise.
        """
        external_tools = settings.external_tools

        if not external_tools.repak or not external_tools.repak.exists():
            return False
        if not external_tools.uassetgui or not external_tools.uassetgui.exists():
            return False

        return True

    def _check_configuration(self) -> bool:
        """Check if catalog builder is properly configured.

        Returns:
            bool: True if all required tools are configured, False otherwise
        """
        return self.requirements_met(self.settings)

    def _get_default_pak_directory(self) -> str:
        """Get default directory for PAK files based on platform.

        Returns:
            str: Default directory path for PAK files
        """
        default_path = Path.cwd()
        system = platform.system()

        if system == "Windows":
            steam_path = Path(
                "C:/Program Files (x86)/Steam/steamapps/common/Foxhole/War/Content/Paks"
            )
            if steam_path.exists():
                default_path = steam_path
        elif system == "Linux":
            try:
                with open("/proc/version") as f:
                    version_info = f.read().lower()
                    if "microsoft" in version_info or "wsl" in version_info:
                        wsl_path = Path(
                            "/mnt/c/Program Files (x86)/Steam/steamapps/common/"
                            "Foxhole/War/Content/Paks"
                        )
                        if wsl_path.exists():
                            default_path = wsl_path
            except OSError:
                pass

        return str(default_path)

    def select_pak_file(self) -> None:
        """Open file dialog to select PAK file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("catalog_builder.select_pak"),
            self._get_default_pak_directory(),
            t("catalog_builder.pak_filter"),
        )
        if file_path:
            self.pak_file = file_path
            self.pak_display.setText(file_path)

    def select_output_path(self) -> None:
        """Open file dialog to select output catalog path."""
        current_path = self.output_path_input.text().strip()
        start_dir = str(Path(current_path).parent) if current_path else str(Path.cwd())

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            t("catalog_builder.select_output"),
            start_dir,
            t("catalog_builder.json_filter"),
        )
        if file_path:
            if not file_path.endswith(".json"):
                file_path += ".json"
            self.output_path_input.setText(file_path)

    def validate_inputs(self) -> tuple[bool, str]:
        """Validate user inputs before starting build.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        if not self.pak_file:
            return False, t("catalog_builder.validation.select_pak")

        if not Path(self.pak_file).exists():
            return False, t("catalog_builder.validation.pak_not_exist")

        output_path = self.output_path_input.text().strip()
        if not output_path:
            return False, t("catalog_builder.validation.specify_output")

        return True, ""

    def start_build(self) -> None:
        """Start the catalog build process."""
        is_valid, error_msg = self.validate_inputs()
        if not is_valid:
            QMessageBox.warning(self, t("common.validation_error"), error_msg)
            return

        # Disable inputs
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.pak_browse_button.setEnabled(False)
        self.output_path_input.setEnabled(False)
        self.workers_spinbox.setEnabled(False)

        # Clear logs
        self.clear_logs()

        # Add log handler
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        configured_level = getattr(logging, self.settings.logging.log_level.upper(), logging.INFO)
        root_logger.setLevel(configured_level)

        # Create and start worker
        self.build_worker = CatalogBuilderWorker(
            pak_file=Path(self.pak_file),  # type: ignore[arg-type]
            output_path=Path(self.output_path_input.text().strip()),
            extractor_tool=self.settings.external_tools.repak,  # type: ignore[arg-type]
            converter_tool=self.settings.external_tools.uassetgui,  # type: ignore[arg-type]
            workers=self.workers_spinbox.value(),
        )
        self.build_worker.finished.connect(self.on_build_finished)
        self.build_worker.error.connect(self.on_build_error)
        self.build_worker.progress.connect(self.on_build_progress)
        self.build_worker.start()

        logger.info("Catalog build process started")

    def cancel_build(self) -> None:
        """Cancel the running build process."""
        if self.build_worker and self.build_worker.isRunning():
            logger.warning("User requested build cancellation")
            self.build_worker.stop()
            self.build_worker.wait()
            self.on_build_finished(False)

    def on_build_finished(self, success: bool) -> None:
        """Handle build process completion.

        Args:
            success (bool): Whether the build was successful
        """
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_handler)

        if success:
            status_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": "INFO",
                "module": "catalog_builder",
                "message": t("catalog_builder.build_completed"),
                "color": "#00FF00",
            }
        else:
            status_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": "WARNING",
                "module": "catalog_builder",
                "message": t("catalog_builder.build_cancelled"),
                "color": "#FFA500",
            }
        self.append_log(status_log)

        # Re-enable inputs
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.pak_browse_button.setEnabled(True)
        self.output_path_input.setEnabled(True)
        self.workers_spinbox.setEnabled(True)

    def on_build_error(self, error_msg: str) -> None:
        """Handle build process error.

        Args:
            error_msg (str): Error message
        """
        error_log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": "ERROR",
            "module": "catalog_builder",
            "message": t("catalog_builder.build_error").replace("{error}", error_msg),
            "color": "#FF0000",
        }
        self.append_log(error_log)

    def on_build_progress(self, message: str) -> None:
        """Handle build progress update.

        Args:
            message (str): Progress message
        """
        progress_log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": "INFO",
            "module": "catalog_builder",
            "message": message,
            "color": "#2196F3",
        }
        self.append_log(progress_log)

    def append_log(self, log_data: dict[str, str]) -> None:
        """Append a log entry to the log display.

        Args:
            log_data (dict[str, str]): Dictionary containing log data
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
        message_item.setTextAlignment(int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop))

        self.log_display.setItem(row_position, 0, time_item)
        self.log_display.setItem(row_position, 1, level_item)
        self.log_display.setItem(row_position, 2, module_item)
        self.log_display.setItem(row_position, 3, message_item)

        self.log_display.resizeRowToContents(row_position)
        self.log_display.scrollToBottom()

    def clear_logs(self) -> None:
        """Clear the log display."""
        self.log_display.setRowCount(0)

    def _log_key_press_event(self, event: QKeyEvent | None) -> None:
        """Handle key press events in log display.

        Args:
            event (QKeyEvent | None): Key event
        """
        if not event:
            return

        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selected_logs()
        else:
            QTableWidget.keyPressEvent(self.log_display, event)

    def _copy_selected_logs(self) -> None:
        """Copy selected log rows to clipboard."""
        selected_rows = self.log_display.selectionModel()
        if not selected_rows:
            return

        selected_indexes = selected_rows.selectedRows()
        if not selected_indexes:
            return

        lines = []
        for index in sorted(selected_indexes, key=lambda x: x.row()):
            row = index.row()
            time_item = self.log_display.item(row, 0)
            level_item = self.log_display.item(row, 1)
            module_item = self.log_display.item(row, 2)
            message_item = self.log_display.item(row, 3)

            if time_item and level_item and module_item and message_item:
                line = (
                    f"[{time_item.text()}] {level_item.text()} "
                    f"{module_item.text()}: {message_item.text()}"
                )
                lines.append(line)

        if lines:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText("\n".join(lines))

    def closeEvent(self, event: object) -> None:
        """Handle window close event.

        Args:
            event (object): Close event
        """
        if self.build_worker and self.build_worker.isRunning():
            reply = QMessageBox.question(
                self,
                t("catalog_builder.build_in_progress_title"),
                t("catalog_builder.build_in_progress_message"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.build_worker.stop()
                self.build_worker.wait()
                self._cleanup_and_accept(event)
            else:
                event.ignore()  # type: ignore[attr-defined]
        else:
            self._cleanup_and_accept(event)

    def _cleanup_and_accept(self, event: object) -> None:
        """Clean up resources and accept close event.

        Args:
            event (object): Close event
        """
        self.log_handler.close()
        event.accept()  # type: ignore[attr-defined]
