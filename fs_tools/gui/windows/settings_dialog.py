"""General fs-tools configuration dialog."""

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.constants import DATA_DOWNLOAD_URL
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.gui.utils.config_manager import ConfigManager
from foxhole_stockpiles.i18n import (
    get_available_languages,
    off_language_changed,
    on_language_changed,
    set_language,
    t,
)
from fs_tools.gui.widgets.config_tabs.database_builder_tab import DatabaseBuilderTab
from fs_tools.gui.widgets.config_tabs.external_tools_tab import ExternalToolsTab

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog for configuring the shared fs-tools settings.

    This dialog configures everything fs-tools relies on:
    - Template database path (scanner.database_path)
    - External tools: repak, umodel and uassetgui
    - Database builder settings: catalog file and resolutions

    All values are persisted to the shared config file (see
    ``foxhole_stockpiles.core.settings.config_path``).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the settings dialog.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.init_ui()
        self._load_current_settings()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        # Wide (golden-ratio proportioned). The height is fitted to the content
        # the first time the dialog is shown (see showEvent), so the whole form
        # is visible without a scrollbar on every platform.
        self._dialog_width = round(740 * 1.618)
        self.setMinimumWidth(self._dialog_width)
        self._height_fitted = False

        outer_layout = QVBoxLayout(self)

        # Info header
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "QLabel { background-color: palette(alternate-base); padding: 10px; "
            "border: 2px solid #2196F3; }"
        )
        outer_layout.addWidget(self.info_label)

        # Scrollable content area (the combined sections can be tall).
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        # Language group
        self.language_group = QGroupBox()
        language_layout = QFormLayout()
        self.language_group.setLayout(language_layout)

        self.language_label = QLabel()
        self.language_input = QComboBox()
        for code, name in get_available_languages():
            self.language_input.addItem(name, code)
        language_layout.addRow(self.language_label, self.language_input)

        layout.addWidget(self.language_group)

        # Database path group
        self.database_group = QGroupBox()
        database_layout = QFormLayout()
        self.database_group.setLayout(database_layout)

        self.database_label = QLabel()
        database_path_layout = QHBoxLayout()
        self.database_path_input = QLineEdit()
        self.database_path_input.textChanged.connect(self._update_db_download_visibility)
        database_path_layout.addWidget(self.database_path_input)
        # Download button (shown only while the field is empty), mirroring the
        # External Tools tab convention.
        self.database_download_btn = QPushButton()
        self.database_download_btn.setMaximumWidth(80)
        self.database_download_btn.clicked.connect(self._open_data_url)
        database_path_layout.addWidget(self.database_download_btn)
        self.database_browse_btn = QPushButton()
        self.database_browse_btn.clicked.connect(self._browse_database)
        database_path_layout.addWidget(self.database_browse_btn)
        database_layout.addRow(self.database_label, database_path_layout)

        layout.addWidget(self.database_group)

        # External tools (all three tools fs-tools may use)
        self.external_tools_tab = ExternalToolsTab(
            show_repak=True,
            show_umodel=True,
            show_uassetgui=True,
        )
        layout.addWidget(self.external_tools_tab)

        # Database builder settings
        self.db_builder_tab = DatabaseBuilderTab()
        layout.addWidget(self.db_builder_tab)

        # The two tab widgets wrap their group boxes in a layout that adds its
        # own margins, which would make those sections narrower than the
        # directly-added Language/Database boxes. Drop the wrapper margins so
        # every section rectangle spans the same width.
        for tab in (self.external_tools_tab, self.db_builder_tab):
            tab_layout = tab.layout()
            if tab_layout is not None:
                tab_layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch()

        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)
        self._scroll_area = scroll_area
        self._scroll_content = content

        # Status label for error messages
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("QLabel { color: red; padding: 5px; }")
        self.status_label.hide()
        outer_layout.addWidget(self.status_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        outer_layout.addWidget(button_box)

        # Apply translations
        self.retranslate()
        self._update_db_download_visibility()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def showEvent(self, event: QShowEvent) -> None:
        """Fit the dialog height to its content the first time it is shown.

        Args:
            event (QShowEvent): The show event.
        """
        super().showEvent(event)
        if not self._height_fitted:
            self._height_fitted = True
            self._fit_height_to_content()

    def _fit_height_to_content(self) -> None:
        """Grow the dialog so the whole form fits without a vertical scrollbar.

        The non-scrolling chrome (info header, buttons, margins) is measured
        directly as ``dialog height - viewport height`` and added to the
        content's height hint, so the height adapts to each platform's font and
        DPI metrics. A small slack is added so metric rounding never trips a
        scrollbar; any surplus simply shows as empty space, which is fine.
        """
        chrome = self.height() - self._scroll_area.viewport().height()
        slack = 8
        needed = chrome + self._scroll_content.sizeHint().height() + slack

        # Never grow past the available screen height (fall back to the
        # computed value if no screen is reported yet).
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            needed = min(needed, screen.availableGeometry().height() - 80)

        self.resize(self._dialog_width, needed)

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event.

        Args:
            _language (str): The new language code (unused).
        """
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("settings_dialog.title"))
        self.info_label.setText(t("settings_dialog.info"))
        self.language_group.setTitle(t("settings_dialog.language_group"))
        self.language_label.setText(t("settings_dialog.language"))
        self.language_label.setToolTip(t("settings_dialog.language_tooltip"))
        self.database_group.setTitle(t("settings_dialog.database_group"))
        self.database_label.setText(t("settings_dialog.database_path"))
        self.database_label.setToolTip(t("settings_dialog.database_tooltip"))
        self.database_path_input.setPlaceholderText(t("settings_dialog.database_placeholder"))
        self.database_download_btn.setText(t("common.download"))
        self.database_browse_btn.setText(t("common.browse"))

    def _update_db_download_visibility(self) -> None:
        """Show the download button only while no database path is set."""
        self.database_download_btn.setVisible(not self.database_path_input.text().strip())

    def _open_data_url(self) -> None:
        """Open the repository data folder in the default browser."""
        QDesktopServices.openUrl(QUrl(DATA_DOWNLOAD_URL))

    def _browse_database(self) -> None:
        """Open file dialog to select the template database file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings_dialog.select_database"),
            "",
            "HDF5 Database (*.h5);;All Files (*)",
        )
        if file_path:
            self.database_path_input.setText(file_path)

    def _load_current_settings(self) -> None:
        """Load current settings into the widgets."""
        settings = get_settings()
        lang_index = self.language_input.findData(settings.gui.language)
        if lang_index >= 0:
            self.language_input.setCurrentIndex(lang_index)
        self.database_path_input.setText(
            str(settings.scanner.database_path) if settings.scanner.database_path else ""
        )
        self.external_tools_tab.set_values(settings.external_tools)
        self.db_builder_tab.set_values(settings.database_builder)

    def _save_and_accept(self) -> None:
        """Save settings and accept the dialog."""
        current_settings = get_settings()

        selected_language: str = self.language_input.currentData() or "en"
        new_gui = current_settings.gui.model_copy(update={"language": selected_language})
        database_text = self.database_path_input.text().strip()
        new_scanner = current_settings.scanner.model_copy(
            update={"database_path": Path(database_text) if database_text else None}
        )
        new_external_tools = self.external_tools_tab.merge_with_existing(
            current_settings.external_tools
        )
        new_db_builder_settings = self.db_builder_tab.get_values()

        updated_settings = current_settings.model_copy(
            update={
                "gui": new_gui,
                "scanner": new_scanner,
                "external_tools": new_external_tools,
                "database_builder": new_db_builder_settings,
            }
        )

        try:
            success, msg = self.config_manager.save_config(updated_settings)
        except Exception as e:  # noqa: BLE001 - surface any save failure to the user
            logger.error("Failed to save settings: %s", e)
            self.status_label.setText(f"Error: {e}")
            self.status_label.show()
            return

        if success:
            logger.info("fs-tools settings saved successfully")
            # Apply the language immediately so open windows retranslate.
            if selected_language != current_settings.gui.language:
                set_language(selected_language)
            self.accept()
        else:
            logger.error("Failed to save settings: %s", msg)
            self.status_label.setText(f"Failed to save: {msg}")
            self.status_label.show()
