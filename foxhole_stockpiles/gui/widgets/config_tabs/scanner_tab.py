"""Scanner settings tab."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.constants import DATA_DOWNLOAD_URL
from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from foxhole_stockpiles.gui.widgets.capture_key_dialog import CaptureKeyDialog
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class ScannerTab(QWidget):
    """Tab for Scanner configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the Scanner tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._capture_key_value: str | None = None
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        self._form_layout = QFormLayout()
        main_layout.addLayout(self._form_layout)

        # Database Path (required)
        self.db_label = QLabel()
        db_layout_widget = QWidget()
        db_layout = QHBoxLayout(db_layout_widget)
        db_layout.setContentsMargins(0, 0, 0, 0)
        self.database_path_input = QLineEdit()
        self.database_path_input.textChanged.connect(self._update_db_download_visibility)
        # Download button (shown only while the field is empty), mirroring the
        # fs-tools External Tools tab convention.
        self.db_download = QPushButton()
        self.db_download.setMaximumWidth(80)
        self.db_download.clicked.connect(self._open_data_url)
        self.db_browse = QPushButton()
        self.db_browse.clicked.connect(self.browse_database)
        db_layout.addWidget(self.database_path_input)
        db_layout.addWidget(self.db_download)
        db_layout.addWidget(self.db_browse)
        self._form_layout.addRow(self.db_label, db_layout_widget)

        # Capture Hotkey
        self.capture_key_label = QLabel()
        key_layout_widget = QWidget()
        key_layout = QHBoxLayout(key_layout_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.capture_key_display = QLineEdit()
        self.capture_key_display.setReadOnly(True)
        self.capture_key_change = QPushButton()
        self.capture_key_change.clicked.connect(self.change_capture_key)
        self.capture_key_clear = QPushButton()
        self.capture_key_clear.clicked.connect(self.clear_capture_key)
        key_layout.addWidget(self.capture_key_display)
        key_layout.addWidget(self.capture_key_change)
        key_layout.addWidget(self.capture_key_clear)
        self._form_layout.addRow(self.capture_key_label, key_layout_widget)

        # Early Exit Threshold (used by fs-tools' candidate inspector)
        self.early_exit_label = QLabel()
        self.early_exit_input = QDoubleSpinBox()
        self.early_exit_input.setRange(0.0, 1.0)
        self.early_exit_input.setSingleStep(0.01)
        self.early_exit_input.setDecimals(3)
        self.early_exit_input.setValue(0.0)
        self._form_layout.addRow(self.early_exit_label, self.early_exit_input)

        # Confidence Gap
        self.confidence_gap_label = QLabel()
        self.confidence_gap_input = QDoubleSpinBox()
        self.confidence_gap_input.setRange(0.0, 1.0)
        self.confidence_gap_input.setSingleStep(0.01)
        self.confidence_gap_input.setDecimals(3)
        self.confidence_gap_input.setValue(0.0)
        self._form_layout.addRow(self.confidence_gap_label, self.confidence_gap_input)

        # Screenshots Folder
        self.screenshots_label = QLabel()
        screenshots_layout_widget = QWidget()
        screenshots_layout = QHBoxLayout(screenshots_layout_widget)
        screenshots_layout.setContentsMargins(0, 0, 0, 0)
        self.screenshots_folder_input = QLineEdit()
        self.screenshots_browse = QPushButton()
        self.screenshots_browse.clicked.connect(self.browse_screenshots)
        screenshots_layout.addWidget(self.screenshots_folder_input)
        screenshots_layout.addWidget(self.screenshots_browse)
        self._form_layout.addRow(self.screenshots_label, screenshots_layout_widget)

        main_layout.addStretch()

        # Apply translations
        self.retranslate()
        self._update_db_download_visibility()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        # Database Path
        self.db_label.setText(t("scanner_tab.database_path"))
        self.db_label.setToolTip(t("scanner_tab.database_path_tooltip"))
        self.database_path_input.setPlaceholderText(t("scanner_tab.database_path_placeholder"))
        self.db_download.setText(t("common.download"))
        self.db_browse.setText(t("common.browse"))

        # Capture Hotkey
        self.capture_key_label.setText(t("scanner_tab.capture_hotkey"))
        self.capture_key_label.setToolTip(t("scanner_tab.capture_hotkey_tooltip"))
        self.capture_key_display.setPlaceholderText(t("scanner_tab.capture_hotkey_placeholder"))
        self.capture_key_change.setText(t("scanner_tab.capture_change"))
        self.capture_key_clear.setText(t("common.clear"))

        # Early Exit Threshold
        self.early_exit_label.setText(t("scanner_tab.early_exit"))
        self.early_exit_label.setToolTip(t("scanner_tab.early_exit_tooltip"))

        # Confidence Gap
        self.confidence_gap_label.setText(t("scanner_tab.confidence_gap"))
        self.confidence_gap_label.setToolTip(t("scanner_tab.confidence_gap_tooltip"))

        # Screenshots Folder
        self.screenshots_label.setText(t("scanner_tab.screenshots_folder"))
        self.screenshots_label.setToolTip(t("scanner_tab.screenshots_folder_tooltip"))
        self.screenshots_folder_input.setPlaceholderText(
            t("scanner_tab.screenshots_folder_placeholder")
        )
        self.screenshots_browse.setText(t("common.browse"))

    def change_capture_key(self) -> None:
        """Open the key-capture dialog and store the chosen hotkey."""
        dialog = CaptureKeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.key_text:
            self._capture_key_value = dialog.key_text
            self.capture_key_display.setText(dialog.key_text)

    def clear_capture_key(self) -> None:
        """Clear the configured capture hotkey."""
        self._capture_key_value = None
        self.capture_key_display.clear()

    def _update_db_download_visibility(self) -> None:
        """Show the download button only while no database path is set."""
        self.db_download.setVisible(not self.database_path_input.text().strip())

    def _open_data_url(self) -> None:
        """Open the repository data folder in the default browser."""
        QDesktopServices.openUrl(QUrl(DATA_DOWNLOAD_URL))

    def browse_database(self) -> None:
        """Open file dialog for database path."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            t("scanner_tab.select_database"),
            "",
            "HDF5 Files (*.h5);;All Files (*)",
        )
        if filepath:
            self.database_path_input.setText(filepath)

    def browse_screenshots(self) -> None:
        """Open folder dialog for the screenshots folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            t("scanner_tab.select_screenshots"),
            "",
        )
        if folder:
            self.screenshots_folder_input.setText(folder)

    def set_values(self, settings: ScannerSettings) -> None:
        """Set widget values from settings.

        Args:
            settings (ScannerSettings): ScannerSettings instance to load values from.
        """
        self.database_path_input.setText(
            str(settings.database_path) if settings.database_path else ""
        )
        self._capture_key_value = settings.capture_key
        self.capture_key_display.setText(settings.capture_key or "")
        self.early_exit_input.setValue(settings.early_exit_threshold)
        self.confidence_gap_input.setValue(settings.confidence_gap)
        self.screenshots_folder_input.setText(settings.screenshots_folder or "")

    def get_values(self) -> ScannerSettings:
        """Get current values from widgets.

        Returns:
            ScannerSettings: ScannerSettings instance with current values from widgets
        """
        db_path_text = self.database_path_input.text()
        return ScannerSettings(
            database_path=Path(db_path_text) if db_path_text else None,
            capture_key=self._capture_key_value or None,
            early_exit_threshold=self.early_exit_input.value(),
            confidence_gap=self.confidence_gap_input.value(),
            screenshots_folder=self.screenshots_folder_input.text() or "",
        )
