"""Icon import window for importing new icons to the database."""

import logging
import os
import platform
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDragEnterEvent, QDropEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
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
from fs_tools.gui.utils.icon_import_worker import IconImportWorker
from fs_tools.gui.utils.pak_validation_worker import PakValidationWorker
from fs_tools.models.pak_validation_result import PakValidationResult

logger = logging.getLogger(__name__)


class IconImportWindow(QMainWindow):
    """Window for importing new icons to the database."""

    # Signal emitted when database is successfully updated (passes the database path)
    database_updated = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the icon import window.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.import_worker: IconImportWorker | None = None
        self.validation_worker: PakValidationWorker | None = None
        self.vanilla_pak_file: str | None = None
        self.mod_pak_files: list[str] = []

        # Validation state for mod PAK files
        self._validation_result: PakValidationResult | None = None
        self._is_validating = False

        # Validation state for vanilla PAK file
        self._vanilla_validation_result: PakValidationResult | None = None
        self._is_validating_vanilla = False
        self.vanilla_validation_worker: PakValidationWorker | None = None

        # The launcher only enables this window once it is configured, so the
        # full UI is always built.
        self.settings = get_settings()

        # Setup log handler (shared across all imports)
        # Use log level from settings
        self.log_handler = QtLogHandler()
        self.log_handler.log_message.connect(self.append_log)
        log_level = getattr(logging, self.settings.logging.log_level.upper(), logging.INFO)
        self.log_handler.setLevel(log_level)

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setGeometry(100, 100, 900, 700)
        self._cpu_count = os.cpu_count() or 1

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Vanilla PAK Section (initially hidden, shown when mod PAK lacks required assets)
        self.vanilla_group = QGroupBox()
        vanilla_layout = QVBoxLayout()
        self.vanilla_group.setLayout(vanilla_layout)

        # Warning text about vanilla PAK
        self.vanilla_info = QLabel()
        self.vanilla_info.setWordWrap(True)
        self.vanilla_info.setStyleSheet(
            "QLabel { "
            "border: 2px solid #FF9800; "
            "border-radius: 4px; "
            "padding: 6px; "
            "font-size: 11px; "
            "background-color: palette(alternate-base); "
            "}"
        )
        vanilla_layout.addWidget(self.vanilla_info)

        # Vanilla PAK file path display
        vanilla_path_layout = QHBoxLayout()
        self.vanilla_pak_display = QLineEdit()
        self.vanilla_pak_display.setReadOnly(True)
        vanilla_path_layout.addWidget(self.vanilla_pak_display)

        # Vanilla PAK buttons
        self.vanilla_browse_button = QPushButton()
        self.vanilla_browse_button.clicked.connect(self.select_vanilla_pak)
        vanilla_path_layout.addWidget(self.vanilla_browse_button)

        self.vanilla_clear_button = QPushButton()
        self.vanilla_clear_button.clicked.connect(self.clear_vanilla_pak)
        vanilla_path_layout.addWidget(self.vanilla_clear_button)

        vanilla_layout.addLayout(vanilla_path_layout)

        layout.addWidget(self.vanilla_group)

        # Initially hide vanilla section until validation shows it's needed
        self.vanilla_group.setVisible(False)

        # Mod PAK Files Section
        self.mod_pak_group = QGroupBox()
        mod_pak_layout = QVBoxLayout()
        self.mod_pak_group.setLayout(mod_pak_layout)

        # Warning about single mod only
        self.mod_warning = QLabel()
        self.mod_warning.setWordWrap(True)
        self.mod_warning.setStyleSheet(
            "QLabel { "
            "border: 2px solid #FF9800; "
            "border-radius: 4px; "
            "padding: 6px; "
            "font-size: 11px; "
            "background-color: palette(alternate-base); "
            "}"
        )
        mod_pak_layout.addWidget(self.mod_warning)

        # Mod PAK file list
        self.mod_pak_list_widget = QListWidget()
        self.mod_pak_list_widget.setAcceptDrops(True)
        self.mod_pak_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.mod_pak_list_widget.dragEnterEvent = self.pak_drag_enter_event  # type: ignore[method-assign]
        self.mod_pak_list_widget.dropEvent = self.pak_drop_event  # type: ignore[method-assign]
        # Limit height to 5 rows
        self.mod_pak_list_widget.setMaximumHeight(100)
        mod_pak_layout.addWidget(self.mod_pak_list_widget)

        # Mod PAK file buttons
        mod_pak_buttons_layout = QHBoxLayout()
        self.add_mod_pak_button = QPushButton()
        self.add_mod_pak_button.clicked.connect(self.add_mod_pak_files)
        mod_pak_buttons_layout.addWidget(self.add_mod_pak_button)

        self.remove_mod_pak_button = QPushButton()
        self.remove_mod_pak_button.clicked.connect(self.remove_selected_mod_paks)
        mod_pak_buttons_layout.addWidget(self.remove_mod_pak_button)

        self.clear_mod_pak_button = QPushButton()
        self.clear_mod_pak_button.clicked.connect(self.clear_all_mod_paks)
        mod_pak_buttons_layout.addWidget(self.clear_mod_pak_button)

        mod_pak_layout.addLayout(mod_pak_buttons_layout)

        layout.addWidget(self.mod_pak_group)

        # Configuration Section
        self.config_group = QGroupBox()
        config_layout = QVBoxLayout()
        self.config_group.setLayout(config_layout)

        # Mod name
        mod_name_layout = QHBoxLayout()
        self.mod_name_label = QLabel()
        mod_name_layout.addWidget(self.mod_name_label)
        self.mod_name_input = QLineEdit()
        mod_name_layout.addWidget(self.mod_name_input)
        config_layout.addLayout(mod_name_layout)

        # Overwrite option
        self.overwrite_checkbox = QCheckBox()
        config_layout.addWidget(self.overwrite_checkbox)

        # Database path row
        db_path_layout = QHBoxLayout()
        self.db_path_label = QLabel()
        db_path_layout.addWidget(self.db_path_label)
        self.db_path_input = QLineEdit()
        db_path = self.settings.scanner.database_path
        self.db_path_input.setText(str(db_path) if db_path else "")
        db_path_layout.addWidget(self.db_path_input)

        self.db_browse_button = QPushButton()
        self.db_browse_button.clicked.connect(self.select_database_path)
        db_path_layout.addWidget(self.db_browse_button)
        config_layout.addLayout(db_path_layout)

        # Workers row
        configured_workers = self.settings.database_builder.workers
        default_workers = configured_workers if configured_workers is not None else self._cpu_count
        workers_layout = QHBoxLayout()
        self.workers_label = QLabel()
        workers_layout.addWidget(self.workers_label)
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setMinimum(1)
        self.workers_spinbox.setMaximum(self._cpu_count)
        self.workers_spinbox.setValue(min(default_workers, self._cpu_count))
        self.workers_spinbox.setFixedWidth(80)
        workers_layout.addWidget(self.workers_spinbox)
        self.workers_hint = QLabel()
        self.workers_hint.setStyleSheet("color: gray; font-size: 11px;")
        workers_layout.addWidget(self.workers_hint)
        workers_layout.addStretch()
        config_layout.addLayout(workers_layout)

        layout.addWidget(self.config_group)

        # Logs Section
        self.logs_group = QGroupBox()
        logs_layout = QVBoxLayout()
        self.logs_group.setLayout(logs_layout)

        self.log_display = QTableWidget()
        self.log_display.setColumnCount(4)
        self.log_display.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_display.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_display.setWordWrap(True)  # Enable word wrap for multi-line content
        vertical_header = self.log_display.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)
            # Auto-resize rows to fit content
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

        # Set minimum column widths
        self.log_display.setColumnWidth(0, 150)  # Time
        self.log_display.setColumnWidth(1, 80)  # Level
        self.log_display.setColumnWidth(2, 250)  # Module

        # Enable copy on CTRL-C
        self.log_display.keyPressEvent = self._log_key_press_event  # type: ignore[method-assign]

        logs_layout.addWidget(self.log_display)

        layout.addWidget(self.logs_group, stretch=1)  # Expand to use maximum available space

        # Action Buttons (at bottom)
        action_buttons_layout = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.clicked.connect(self.start_import)
        action_buttons_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.cancel_import)
        self.cancel_button.setEnabled(False)
        action_buttons_layout.addWidget(self.cancel_button)

        # Validation status label (shows validation state)
        self.validation_status_label = QLabel("")
        self.validation_status_label.setStyleSheet("font-size: 11px;")
        action_buttons_layout.addWidget(self.validation_status_label)

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
        self.setWindowTitle(t("database_builder.title"))
        self.vanilla_group.setTitle(t("database_builder.vanilla_group"))
        self.vanilla_info.setText(t("database_builder.vanilla_warning"))
        self.vanilla_pak_display.setPlaceholderText(t("database_builder.no_vanilla_selected"))
        self.vanilla_browse_button.setText(t("common.browse"))
        self.vanilla_clear_button.setText(t("common.clear"))
        self.mod_pak_group.setTitle(t("database_builder.mod_pak_group"))
        self.mod_warning.setText(t("database_builder.mod_pak_warning"))
        self.add_mod_pak_button.setText(t("database_builder.add_pak_files"))
        self.remove_mod_pak_button.setText(t("database_builder.remove_selected"))
        self.clear_mod_pak_button.setText(t("common.clear_all"))
        self.config_group.setTitle(t("database_builder.configuration_group"))
        self.mod_name_label.setText(t("database_builder.mod_name"))
        self.mod_name_input.setPlaceholderText(t("database_builder.mod_name_placeholder"))
        self.overwrite_checkbox.setText(t("database_builder.overwrite"))
        self.overwrite_checkbox.setToolTip(t("database_builder.overwrite_tooltip"))
        self.db_path_label.setText(t("database_builder.destination_database"))
        self.db_path_input.setPlaceholderText(t("database_builder.destination_placeholder"))
        self.db_path_input.setToolTip(t("database_builder.destination_tooltip"))
        self.db_browse_button.setText(t("common.browse"))
        self.workers_label.setText(t("database_builder.workers"))
        self.workers_spinbox.setToolTip(t("database_builder.workers_tooltip"))
        self.workers_hint.setText(
            t("database_builder.cores_detected").replace("{cores}", str(self._cpu_count))
        )
        self.logs_group.setTitle(t("database_builder.process_logs"))
        self.log_display.setHorizontalHeaderLabels(
            [
                t("common.log_columns.time"),
                t("common.log_columns.level"),
                t("common.log_columns.module"),
                t("common.log_columns.message"),
            ]
        )
        self.start_button.setText(t("database_builder.start_import"))
        self.cancel_button.setText(t("common.cancel"))
        self.clear_logs_button.setText(t("common.clear_logs"))
        self.close_button.setText(t("common.close"))

    @staticmethod
    def requirements_met(settings: AppSettings) -> bool:
        """Return whether the database builder has everything it needs.

        Args:
            settings (AppSettings): The settings to check.

        Returns:
            bool: True if repak, umodel and the catalog file are all configured
                and exist on disk, False otherwise.
        """
        external_tools = settings.external_tools
        db_builder = settings.database_builder

        if not external_tools.repak or not external_tools.repak.exists():
            return False
        if not external_tools.umodel or not external_tools.umodel.exists():
            return False
        if not db_builder.catalog_file or not db_builder.catalog_file.exists():
            return False

        return True

    def _get_default_pak_directory(self) -> str:
        """Get default directory for PAK files based on platform.

        Returns:
            str: Default directory path for PAK files
        """
        # Default to current working directory
        default_path = Path.cwd()
        system = platform.system()

        if system == "Windows":
            # Windows: C:\Program Files (x86)\Steam\steamapps\common\Foxhole\War\Content\Paks
            steam_path = Path(
                "C:/Program Files (x86)/Steam/steamapps/common/Foxhole/War/Content/Paks"
            )
            if steam_path.exists():
                default_path = steam_path
        elif system == "Linux":
            # Check if running under WSL
            try:
                with open("/proc/version") as f:
                    version_info = f.read().lower()
                    if "microsoft" in version_info or "wsl" in version_info:
                        # WSL: /mnt/c/Program Files (x86)/Steam/...
                        wsl_path = Path(
                            "/mnt/c/Program Files (x86)/Steam/steamapps/common/"
                            "Foxhole/War/Content/Paks"
                        )
                        if wsl_path.exists():
                            default_path = wsl_path
            except OSError:
                pass  # Keep default_path as cwd

        return str(default_path)

    def select_vanilla_pak(self) -> None:
        """Open file dialog to select vanilla PAK file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("database_builder.select_vanilla_pak"),
            self._get_default_pak_directory(),
            t("database_builder.pak_filter"),
        )
        if file_path:
            self.vanilla_pak_file = file_path
            self.vanilla_pak_display.setText(file_path)
            # Trigger validation to verify vanilla PAK has required assets
            self._trigger_vanilla_validation()

    def clear_vanilla_pak(self) -> None:
        """Clear the vanilla PAK file selection."""
        self.vanilla_pak_file = None
        self.vanilla_pak_display.clear()
        self._vanilla_validation_result = None

        # If mod PAK validation showed missing assets, restore the warning state
        if self._validation_result and not self._validation_result.is_valid:
            self.vanilla_info.setVisible(True)
            self.validation_status_label.setText(t("database_builder.validation.missing_assets"))
            self.validation_status_label.setStyleSheet("color: #FF9800; font-size: 11px;")
            self._update_start_button_state()

    def select_database_path(self) -> None:
        """Open file dialog to select database file."""
        # Start from current path if set, otherwise use current directory
        current_path = self.db_path_input.text().strip()
        start_dir = str(Path(current_path).parent) if current_path else str(Path.cwd())

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            t("database_builder.select_database"),
            start_dir,
            t("database_info_window.database_filter"),
        )
        if file_path:
            # Ensure .h5 extension
            if not file_path.endswith(".h5"):
                file_path += ".h5"
            self.db_path_input.setText(file_path)

    def add_mod_pak_files(self) -> None:
        """Open file dialog to add mod PAK files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            t("database_builder.select_mod_pak"),
            self._get_default_pak_directory(),
            t("database_builder.pak_filter"),
        )
        if files:
            added = False
            for file_path in files:
                if file_path not in self.mod_pak_files:
                    self.mod_pak_files.append(file_path)
                    self.mod_pak_list_widget.addItem(file_path)
                    added = True
            if added:
                self._trigger_validation()

    def remove_selected_mod_paks(self) -> None:
        """Remove selected mod PAK files from the list."""
        selected_items = self.mod_pak_list_widget.selectedItems()
        removed = False
        for item in selected_items:
            row = self.mod_pak_list_widget.row(item)
            self.mod_pak_list_widget.takeItem(row)
            if item.text() in self.mod_pak_files:
                self.mod_pak_files.remove(item.text())
                removed = True
        if removed:
            self._trigger_validation()

    def clear_all_mod_paks(self) -> None:
        """Clear all mod PAK files from the list."""
        self.mod_pak_list_widget.clear()
        self.mod_pak_files.clear()
        # Clear validation state and hide vanilla section
        self._validation_result = None
        self._vanilla_validation_result = None
        self.vanilla_pak_file = None
        self.vanilla_pak_display.clear()
        self.validation_status_label.setText("")
        self.vanilla_group.setVisible(False)
        self._update_start_button_state()

    def pak_drag_enter_event(self, e: QDragEnterEvent | None) -> None:
        """Handle drag enter event for PAK files.

        Args:
            e (QDragEnterEvent | None): Drag event
        """
        if e:
            # Don't accept drags while validating
            if self._is_validating:
                e.ignore()
            else:
                e.accept()

    def pak_drop_event(self, event: QDropEvent | None) -> None:
        """Handle drop event for mod PAK files.

        Args:
            event (QDropEvent | None): Drop event
        """
        if not event:
            return

        # Don't accept drops while validating
        if self._is_validating:
            event.ignore()
            return

        mime_data = event.mimeData()
        added = False
        if mime_data:
            urls = mime_data.urls()
            if urls:
                for url in urls:
                    filepath = url.toLocalFile()
                    if filepath and filepath.endswith(".pak"):
                        if filepath not in self.mod_pak_files:
                            self.mod_pak_files.append(filepath)
                            self.mod_pak_list_widget.addItem(filepath)
                            added = True
        event.accept()
        if added:
            self._trigger_validation()

    def _trigger_validation(self) -> None:
        """Trigger PAK file validation in a background thread."""
        # Don't validate if no PAK files or already validating
        if not self.mod_pak_files:
            return

        # Cancel any existing validation
        if self.validation_worker and self.validation_worker.isRunning():
            self.validation_worker.wait()

        # Check if extractor tool is configured
        extractor_tool = self.settings.external_tools.repak
        if not extractor_tool or not extractor_tool.exists():
            return

        # Disable PAK controls while validating
        self._set_pak_controls_enabled(False)
        self._is_validating = True
        self.validation_status_label.setText(t("database_builder.validation.validating_pak"))
        self.validation_status_label.setStyleSheet("color: #2196F3; font-size: 11px;")
        self._update_start_button_state()

        # Start validation worker
        self.validation_worker = PakValidationWorker(
            pak_files=self.mod_pak_files.copy(),
            extractor_tool=extractor_tool,
            parent=self,
        )
        self.validation_worker.validation_complete.connect(self._on_validation_complete)
        self.validation_worker.start()

    def _on_validation_complete(self, result: PakValidationResult) -> None:
        """Handle validation completion.

        Args:
            result: The validation result
        """
        self._is_validating = False
        self._validation_result = result
        self._set_pak_controls_enabled(True)

        if result.is_valid:
            # PAK files have all required assets - hide vanilla section
            self.validation_status_label.setText(t("database_builder.validation.all_assets_found"))
            self.validation_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            self.vanilla_group.setVisible(False)
            self.clear_vanilla_pak()
        else:
            # PAK files are missing required assets - show vanilla section
            self.validation_status_label.setText(t("database_builder.validation.missing_assets"))
            self.validation_status_label.setStyleSheet("color: #FF9800; font-size: 11px;")
            self.vanilla_group.setVisible(True)

            # Update the info label with specific missing assets
            missing = []
            if not result.has_crate_icon:
                missing.append("crate icon")
            if not result.has_subicons:
                missing.append("subicons")
            missing_text = " and ".join(missing)
            self.vanilla_info.setText(
                t("database_builder.vanilla_warning_missing").replace("{missing}", missing_text)
            )

        self._update_start_button_state()

    def _set_pak_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable PAK file controls.

        Args:
            enabled: Whether to enable or disable controls
        """
        self.add_mod_pak_button.setEnabled(enabled)
        self.remove_mod_pak_button.setEnabled(enabled)
        self.clear_mod_pak_button.setEnabled(enabled)
        self.mod_pak_list_widget.setAcceptDrops(enabled)

    def _trigger_vanilla_validation(self) -> None:
        """Trigger validation of the vanilla PAK file."""
        if not self.vanilla_pak_file:
            return

        extractor_tool = self.settings.external_tools.repak
        if not extractor_tool or not extractor_tool.exists():
            return

        # Disable vanilla PAK controls while validating
        self._set_vanilla_controls_enabled(False)
        self._is_validating_vanilla = True
        self.validation_status_label.setText(t("database_builder.validation.validating_vanilla"))
        self.validation_status_label.setStyleSheet("color: #2196F3; font-size: 11px;")
        self._update_start_button_state()

        # Start validation worker for vanilla PAK only
        self.vanilla_validation_worker = PakValidationWorker(
            pak_files=[self.vanilla_pak_file],
            extractor_tool=extractor_tool,
            parent=self,
        )
        self.vanilla_validation_worker.validation_complete.connect(
            self._on_vanilla_validation_complete
        )
        self.vanilla_validation_worker.start()

    def _on_vanilla_validation_complete(self, result: PakValidationResult) -> None:
        """Handle vanilla PAK validation completion.

        Args:
            result: The validation result
        """
        self._is_validating_vanilla = False
        self._vanilla_validation_result = result
        self._set_vanilla_controls_enabled(True)

        if result.is_valid:
            # Vanilla PAK has all required assets - hide warning and show success
            self.vanilla_info.setVisible(False)
            self.validation_status_label.setText(t("database_builder.validation.all_assets_found"))
            self.validation_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            # Vanilla PAK is missing required assets - this is the wrong file!
            self.vanilla_info.setVisible(True)
            self.validation_status_label.setText(t("database_builder.validation.invalid_vanilla"))
            self.validation_status_label.setStyleSheet("color: #F44336; font-size: 11px;")

            # Show specific error message
            missing = []
            if not result.has_crate_icon:
                missing.append("crate icon")
            if not result.has_subicons:
                missing.append("subicons")
            missing_text = " and ".join(missing)

            QMessageBox.warning(
                self,
                t("database_builder.invalid_vanilla_title"),
                t("database_builder.invalid_vanilla_message").replace("{missing}", missing_text),
            )

        self._update_start_button_state()

    def _set_vanilla_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable vanilla PAK file controls.

        Args:
            enabled: Whether to enable or disable controls
        """
        self.vanilla_browse_button.setEnabled(enabled)
        self.vanilla_clear_button.setEnabled(enabled)

    def _re_enable_inputs(self) -> None:
        """Re-enable input controls after import completes or fails."""
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.mod_name_input.setEnabled(True)
        self.overwrite_checkbox.setEnabled(True)
        self.db_path_input.setEnabled(True)
        self.workers_spinbox.setEnabled(True)

    def _update_start_button_state(self) -> None:
        """Update the start button enabled state based on validation results.

        The start button is disabled when:
        - Validation is in progress (mod or vanilla)
        - Mod PAK validation failed and no valid vanilla PAK is selected
        """
        # Disable if any validation is in progress
        if self._is_validating or self._is_validating_vanilla:
            self.start_button.setEnabled(False)
            return

        # If no mod PAK files selected, enable (will be caught by validate_inputs)
        if not self.mod_pak_files:
            self.start_button.setEnabled(True)
            return

        # If mod PAK validation passed, enable
        if self._validation_result and self._validation_result.is_valid:
            self.start_button.setEnabled(True)
            return

        # If mod PAK validation failed, check vanilla PAK status
        if self._validation_result and not self._validation_result.is_valid:
            # Vanilla PAK must be valid to proceed
            if self._vanilla_validation_result and self._vanilla_validation_result.is_valid:
                self.start_button.setEnabled(True)
            else:
                self.start_button.setEnabled(False)
            return

        # Default: enable (no validation result yet means we haven't validated)
        self.start_button.setEnabled(True)

    def validate_inputs(self) -> tuple[bool, str]:
        """Validate user inputs before starting import.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        if not self.mod_pak_files:
            return False, t("database_builder.validation.add_pak_file")

        # Check if validation is still running
        if self._is_validating:
            return False, t("database_builder.validation.wait_validation")

        if self._is_validating_vanilla:
            return False, t("database_builder.validation.wait_vanilla_validation")

        # Check if vanilla PAK is required but not selected or invalid
        if self._validation_result and not self._validation_result.is_valid:
            if not self.vanilla_pak_file:
                return False, t("database_builder.validation.mod_missing_assets")
            # Check if vanilla PAK was validated and is valid
            if self._vanilla_validation_result and not self._vanilla_validation_result.is_valid:
                return False, t("database_builder.validation.vanilla_invalid")
            # If vanilla PAK selected but not validated yet, wait
            if not self._vanilla_validation_result:
                return False, t("database_builder.validation.wait_vanilla_validation")

        mod_name = self.mod_name_input.text().strip()
        if not mod_name:
            return False, t("database_builder.validation.enter_mod_name")

        db_path = self.db_path_input.text().strip()
        if not db_path:
            return False, t("database_builder.validation.select_database")

        return True, ""

    def start_import(self) -> None:
        """Start the icon import process."""
        # Validate inputs
        is_valid, error_msg = self.validate_inputs()
        if not is_valid:
            QMessageBox.warning(self, t("common.validation_error"), error_msg)
            return

        mod_name = self.mod_name_input.text().strip()
        db_path = Path(self.db_path_input.text().strip())
        self._current_import_db_path = db_path  # Store for signal emission

        # Disable inputs and start button
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.mod_name_input.setEnabled(False)
        self.overwrite_checkbox.setEnabled(False)
        self.db_path_input.setEnabled(False)
        self.workers_spinbox.setEnabled(False)

        # Clear logs
        self.clear_logs()

        # Add log handler to root logger and apply configured log level
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)

        # Apply user's configured log level to root logger
        configured_level = getattr(logging, self.settings.logging.log_level.upper(), logging.INFO)
        root_logger.setLevel(configured_level)

        # Get catalog from settings
        catalog_path = self.settings.database_builder.catalog_file
        if not catalog_path:
            QMessageBox.critical(self, "Error", "Catalog file not configured in settings")
            return

        # Create and start worker
        try:
            self.import_worker = IconImportWorker(
                mod_pak_files=self.mod_pak_files,
                mod_name=mod_name,
                catalog_path=catalog_path,
                overwrite=self.overwrite_checkbox.isChecked(),
                vanilla_pak_file=self.vanilla_pak_file,
                database_path=db_path,
                database_workers=self.workers_spinbox.value(),
            )
        except ValueError as e:
            QMessageBox.critical(self, t("database_builder.invalid_mod_name_title"), str(e))
            logger.error("Invalid mod name: %s", e)
            # Re-enable inputs so user can fix the error
            self._re_enable_inputs()
            return

        self.import_worker.finished.connect(self.on_import_finished)
        self.import_worker.error.connect(self.on_import_error)
        self.import_worker.start()

        logger.info("Icon import process started for mod: %s", mod_name)

    def cancel_import(self) -> None:
        """Cancel the running import process."""
        if self.import_worker and self.import_worker.isRunning():
            logger.warning("User requested import cancellation")
            self.import_worker.stop()
            self.import_worker.wait()
            self.on_import_finished(False)

    def on_import_finished(self, success: bool) -> None:
        """Handle import process completion.

        Args:
            success (bool): Whether the import was successful
        """
        # Remove log handler from root logger (but don't close it - reused for next import)
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_handler)

        # Add final status message to logs

        if success:
            status_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": "INFO",
                "module": "icon_import",
                "message": t("database_builder.import_completed"),
                "color": "#00FF00",  # Green
            }
        else:
            status_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": "WARNING",
                "module": "icon_import",
                "message": t("database_builder.import_cancelled"),
                "color": "#FFA500",  # Orange
            }
        self.append_log(status_log)

        # Re-enable inputs
        self._re_enable_inputs()

        # Emit signal when database was successfully updated
        if success and hasattr(self, "_current_import_db_path"):
            self.database_updated.emit(self._current_import_db_path)

    def on_import_error(self, error_msg: str) -> None:
        """Handle import process error.

        Args:
            error_msg (str): Error message
        """
        # Add error message to logs

        error_log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": "ERROR",
            "module": "icon_import",
            "message": t("database_builder.import_error").replace("{error}", error_msg),
            "color": "#FF0000",  # Red
        }
        self.append_log(error_log)

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
        # Enable text wrapping for message item and align to top
        message_item.setTextAlignment(int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop))

        # Add items to table
        self.log_display.setItem(row_position, 0, time_item)
        self.log_display.setItem(row_position, 1, level_item)
        self.log_display.setItem(row_position, 2, module_item)
        self.log_display.setItem(row_position, 3, message_item)

        # Resize row to fit content
        self.log_display.resizeRowToContents(row_position)

        # Auto-scroll to bottom
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

        # Handle CTRL-C for copying selected rows
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selected_logs()
        else:
            # Call the default implementation for other keys
            QTableWidget.keyPressEvent(self.log_display, event)

    def _copy_selected_logs(self) -> None:
        """Copy selected log rows to clipboard."""
        selected_rows = self.log_display.selectionModel()
        if not selected_rows:
            return

        selected_indexes = selected_rows.selectedRows()
        if not selected_indexes:
            return

        # Build text from selected rows
        lines = []
        for index in sorted(selected_indexes, key=lambda x: x.row()):
            row = index.row()
            time_item = self.log_display.item(row, 0)
            level_item = self.log_display.item(row, 1)
            module_item = self.log_display.item(row, 2)
            message_item = self.log_display.item(row, 3)

            if time_item and level_item and module_item and message_item:
                # Format: [Time] LEVEL Module: Message
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
        if self.import_worker and self.import_worker.isRunning():
            reply = QMessageBox.question(
                self,
                t("database_builder.import_in_progress_title"),
                t("database_builder.import_in_progress_message"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.import_worker.stop()
                self.import_worker.wait()
                self._cleanup_and_accept(event)
            else:
                event.ignore()  # type: ignore[attr-defined]
        else:
            # Stop validation workers if running
            if self.validation_worker and self.validation_worker.isRunning():
                self.validation_worker.wait()
            if self.vanilla_validation_worker and self.vanilla_validation_worker.isRunning():
                self.vanilla_validation_worker.wait()
            self._cleanup_and_accept(event)

    def _cleanup_and_accept(self, event: object) -> None:
        """Clean up resources and accept close event.

        Args:
            event (object): Close event
        """
        # Close the log handler to prevent further emissions
        self.log_handler.close()
        event.accept()  # type: ignore[attr-defined]
