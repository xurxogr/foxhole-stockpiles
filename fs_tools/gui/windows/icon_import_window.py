"""Icon import window for importing new icons to the database."""

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import on_language_changed, t
from fs_tools.core.pak_directory import default_pak_directory
from fs_tools.gui.utils.icon_import_worker import IconImportWorker
from fs_tools.gui.utils.pak_coverage_status import has_catalog_icons
from fs_tools.gui.utils.pak_validation_controller import (
    STATUS_COLOR_WARNING,
    PakValidationController,
)
from fs_tools.gui.windows.process_log_window import ProcessLogWindow

logger = logging.getLogger(__name__)


class IconImportWindow(ProcessLogWindow):
    """Window for importing new icons to the database."""

    # Signal emitted when database is successfully updated (passes the database path)
    database_updated = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the icon import window.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        # The launcher only enables this window once it is configured, so the
        # full UI is always built.
        super().__init__(settings=get_settings(), log_module="icon_import", parent=parent)
        self.import_worker: IconImportWorker | None = None
        self.vanilla_pak_file: str | None = None
        self.mod_pak_files: list[str] = []

        self.pak_validation = PakValidationController(
            view=self, settings=self.settings, parent=self
        )

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setGeometry(100, 100, 900, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        self._build_vanilla_section(layout)
        self._build_mod_pak_section(layout)
        self._build_config_section(layout)
        self._build_logs_section(layout)
        self._build_action_buttons(layout)

        # Apply translations
        self.retranslate()

        # Connect to language change signal with cleanup
        on_language_changed(self._on_language_changed)

    def _build_vanilla_section(self, layout: QVBoxLayout) -> None:
        """Build the vanilla PAK section (hidden until validation requires it).

        Args:
            layout (QVBoxLayout): Parent layout to add the section to.
        """
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

    def _build_mod_pak_section(self, layout: QVBoxLayout) -> None:
        """Build the mod PAK files section.

        Args:
            layout (QVBoxLayout): Parent layout to add the section to.
        """
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

    def _build_config_section(self, layout: QVBoxLayout) -> None:
        """Build the configuration section (mod name and destination database).

        Args:
            layout (QVBoxLayout): Parent layout to add the section to.
        """
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

        layout.addWidget(self.config_group)

    def _build_logs_section(self, layout: QVBoxLayout) -> None:
        """Build the process logs section.

        Args:
            layout (QVBoxLayout): Parent layout to add the section to.
        """
        layout.addWidget(self.logs_group, stretch=1)  # Expand to use maximum available space

    def _build_action_buttons(self, layout: QVBoxLayout) -> None:
        """Build the bottom action buttons row.

        Args:
            layout (QVBoxLayout): Parent layout to add the row to.
        """
        # Action Buttons (at bottom)
        action_buttons_layout = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.clicked.connect(self.start_import)
        action_buttons_layout.addWidget(self.start_button)

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
        self.db_path_label.setText(t("database_builder.destination_database"))
        self.db_path_input.setPlaceholderText(t("database_builder.destination_placeholder"))
        self.db_path_input.setToolTip(t("database_builder.destination_tooltip"))
        self.db_browse_button.setText(t("common.browse"))
        self.logs_group.setTitle(t("database_builder.process_logs"))
        self.log_display.retranslate()
        self.start_button.setText(t("database_builder.start_import"))
        self.clear_logs_button.setText(t("common.clear_logs"))
        self.close_button.setText(t("common.close"))

    @staticmethod
    def requirements_met(settings: AppSettings) -> bool:
        """Return whether the icon importer has everything it needs.

        The PAK files are read directly, so only the catalog is required.

        Args:
            settings (AppSettings): The settings to check.

        Returns:
            bool: True if the catalog file is configured and exists on disk.
        """
        catalog_file = settings.database_builder.catalog_file
        return bool(catalog_file and catalog_file.exists())

    def set_validation_status(self, text: str, color: str) -> None:
        """Show a validation status message.

        Args:
            text (str): The message.
            color (str): The message's CSS color.
        """
        self.validation_status_label.setText(text)
        self.validation_status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def select_vanilla_pak(self) -> None:
        """Open file dialog to select vanilla PAK file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("database_builder.select_vanilla_pak"),
            default_pak_directory(),
            t("database_builder.pak_filter"),
        )
        if file_path:
            self.vanilla_pak_file = file_path
            self.vanilla_pak_display.setText(file_path)
            # Trigger validation to verify vanilla PAK has required assets
            self.pak_validation.trigger_vanilla_validation()

    def clear_vanilla_pak(self) -> None:
        """Clear the vanilla PAK file selection."""
        self.vanilla_pak_file = None
        self.vanilla_pak_display.clear()
        self.pak_validation.vanilla_validation_result = None

        # If the mod PAK files lack overlays, restore the warning state
        if self.pak_validation.mod_needs_vanilla():
            self.vanilla_info.setVisible(True)
            self.set_validation_status(
                text=t("database_builder.validation.missing_assets"), color=STATUS_COLOR_WARNING
            )
            self.pak_validation.update_start_button_state()

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
            default_pak_directory(),
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
                self.pak_validation.trigger_validation()

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
            self.pak_validation.trigger_validation()

    def clear_all_mod_paks(self) -> None:
        """Clear all mod PAK files from the list."""
        self.mod_pak_list_widget.clear()
        self.mod_pak_files.clear()
        # Clear validation state and hide vanilla section
        self.pak_validation.validation_result = None
        self.pak_validation.validation_failed = False
        self.pak_validation.vanilla_validation_result = None
        self.vanilla_pak_file = None
        self.vanilla_pak_display.clear()
        self.validation_status_label.setText("")
        self.vanilla_group.setVisible(False)
        self.pak_validation.update_start_button_state()

    def pak_drag_enter_event(self, e: QDragEnterEvent | None) -> None:
        """Handle drag enter event for PAK files.

        Args:
            e (QDragEnterEvent | None): Drag event
        """
        if e:
            # Don't accept drags while validating
            if self.pak_validation.is_validating:
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
        if self.pak_validation.is_validating:
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
            self.pak_validation.trigger_validation()

    def _re_enable_inputs(self) -> None:
        """Re-enable input controls after import completes or fails."""
        self.start_button.setEnabled(True)
        self.mod_name_input.setEnabled(True)
        self.db_path_input.setEnabled(True)

    def validate_inputs(self) -> tuple[bool, str]:
        """Validate user inputs before starting import.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        if not self.mod_pak_files:
            return False, t("database_builder.validation.add_pak_file")

        # Check if validation is still running
        if self.pak_validation.is_validating:
            return False, t("database_builder.validation.wait_validation")

        if self.pak_validation.is_validating_vanilla:
            return False, t("database_builder.validation.wait_vanilla_validation")

        if self.pak_validation.validation_failed:
            return False, t("database_builder.validation.check_failed", error="")

        if self.pak_validation.validation_result and not has_catalog_icons(
            self.pak_validation.validation_result
        ):
            return False, t("database_builder.validation.no_catalog_icons")

        # Check if vanilla PAK is required but not selected or invalid
        if self.pak_validation.mod_needs_vanilla():
            if not self.vanilla_pak_file:
                return False, t("database_builder.validation.mod_missing_assets")
            # If vanilla PAK selected but not validated yet, wait
            if not self.pak_validation.vanilla_validation_result:
                return False, t("database_builder.validation.wait_vanilla_validation")
            if not self.pak_validation.vanilla_is_valid():
                return False, t("database_builder.validation.vanilla_invalid")

        mod_name = self.mod_name_input.text().strip()
        if not mod_name:
            return False, t("database_builder.validation.enter_mod_name")

        db_path = self.db_path_input.text().strip()
        if not db_path:
            return False, t("database_builder.validation.select_database")

        # The configuration tab only offers supported ones; a hand-edited file may not.
        supported = {resolution.value for resolution in SupportedResolution}
        configured = self.settings.database_builder.target_resolutions or []
        unsupported = [resolution for resolution in configured if resolution not in supported]
        if unsupported:
            return False, t(
                "database_builder.validation.unsupported_resolutions",
                resolutions=", ".join(unsupported),
            )

        return True, ""

    def start_import(self) -> None:
        """Start the icon import process."""
        # Validate inputs
        is_valid, error_msg = self.validate_inputs()
        if not is_valid:
            QMessageBox.warning(self, t("common.validation_error"), error_msg)
            return

        catalog_path = self.settings.database_builder.catalog_file
        if not catalog_path:
            QMessageBox.warning(
                self,
                t("common.validation_error"),
                t("database_builder.validation.catalog_not_configured"),
            )
            return

        mod_name = self.mod_name_input.text().strip()
        db_path = Path(self.db_path_input.text().strip())

        # Create the worker before changing anything, so a refusal has nothing to undo.
        try:
            self.import_worker = IconImportWorker(
                mod_pak_files=self.mod_pak_files,
                mod_name=mod_name,
                catalog_path=catalog_path,
                database_path=db_path,
                vanilla_pak_file=self.vanilla_pak_file,
                resolutions=self._target_resolutions(),
            )
        except ValueError as e:
            QMessageBox.critical(self, t("database_builder.invalid_mod_name_title"), str(e))
            logger.error("Invalid mod name: %s", e)
            return

        self._current_import_db_path = db_path  # Store for signal emission

        # Disable inputs and start button
        self.start_button.setEnabled(False)
        self.mod_name_input.setEnabled(False)
        self.db_path_input.setEnabled(False)

        self.clear_logs()
        self.start_log_capture()

        self.import_worker.finished.connect(self.on_import_finished)
        self.import_worker.error.connect(self.on_import_error)
        self.import_worker.progress.connect(self.on_import_progress)
        self.import_worker.start()

        logger.info("Icon import process started for mod: %s", mod_name)

    def _target_resolutions(self) -> list[int] | None:
        """Return the resolutions configured for imports.

        Returns:
            list[int] | None: The configured resolutions, or None for all of them.
        """
        configured = self.settings.database_builder.target_resolutions
        return [int(resolution) for resolution in configured] if configured else None

    def on_import_finished(self, success: bool) -> None:
        """Handle import process completion.

        Args:
            success (bool): Whether the import was successful
        """
        self.stop_log_capture()

        if success:
            self.log_success(t("database_builder.import_completed"))
        else:
            self.log_warning(t("database_builder.import_cancelled"))

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
        self.log_error(t("database_builder.import_error", error=error_msg))

    def on_import_progress(self, message: str) -> None:
        """Handle import progress update.

        Args:
            message (str): Progress message
        """
        self.log_info(message)

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
                # The import cannot be interrupted safely; let it finish first
                self.import_worker.wait()
                self._cleanup_and_accept(event)
            else:
                event.ignore()  # type: ignore[attr-defined]
        else:
            self.pak_validation.wait_for_workers()
            self._cleanup_and_accept(event)
