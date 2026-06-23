"""Configuration window with tabbed interface for all settings."""

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings import reload_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.gui.utils.config_manager import ConfigManager
from foxhole_stockpiles.gui.widgets.config_tabs.clipboard_tab import ClipboardTab
from foxhole_stockpiles.gui.widgets.config_tabs.general_tab import GeneralTab
from foxhole_stockpiles.gui.widgets.config_tabs.gui_tab import GUITab
from foxhole_stockpiles.gui.widgets.config_tabs.input_tab import InputTab
from foxhole_stockpiles.gui.widgets.config_tabs.logging_tab import LoggingTab
from foxhole_stockpiles.gui.widgets.config_tabs.output_tab import OutputTab
from foxhole_stockpiles.gui.widgets.config_tabs.sav_processing_tab import SavProcessingTab
from foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab import ScannerTab
from foxhole_stockpiles.i18n import (
    get_translator,
    off_language_changed,
    on_language_changed,
    set_language,
    t,
)

logger = logging.getLogger(__name__)


class ConfigWindow(QMainWindow):
    """Configuration window for managing application settings."""

    # Signal emitted when the window is closed
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the configuration window.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.settings: AppSettings | None = None
        # Height is fitted to the tallest tab the first time the window shows,
        # so every option is visible without a scrollbar and no taller.
        self._height_fitted = False

        self.init_ui()
        self.load_settings()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle(t("config_window.title"))
        # Width is fixed; the height is fitted to content on first show.
        self.setGeometry(100, 100, 820, 640)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Add hint about hovering labels at top
        hint_layout = QHBoxLayout()
        self.hint_label = QLabel(t("config_window.tip_hover"))
        self.hint_label.setStyleSheet("QLabel { color: gray; font-size: 11px; }")
        hint_layout.addWidget(self.hint_label)
        hint_layout.addStretch()
        layout.addLayout(hint_layout)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create the per-section sub-tabs. They keep their own set/get_values and
        # settings sections; the visible tabs below group them by role.
        self.scanner_tab = ScannerTab()
        self.output_tab = OutputTab()
        self.logging_tab = LoggingTab()
        self.gui_tab = GUITab()
        self.sav_processing_tab = SavProcessingTab()
        self.clipboard_tab = ClipboardTab()

        # Grouped tabs: Input (the three input sources) and General (interface +
        # logging). Output stays on its own.
        self.input_tab = InputTab(self.scanner_tab, self.sav_processing_tab, self.clipboard_tab)
        self.general_tab = GeneralTab(self.gui_tab, self.logging_tab)

        # Track current language (for retranslation on save)
        self._current_language: str = get_translator().language

        # Build all tabs
        self._build_tabs()

        # Create button box
        button_box = QDialogButtonBox()

        self.save_button = QPushButton(t("common.save"))
        self.save_button.clicked.connect(self.save_settings)
        button_box.addButton(self.save_button, QDialogButtonBox.ButtonRole.AcceptRole)

        self.close_button = QPushButton(t("common.close"))
        self.close_button.clicked.connect(self.close)
        button_box.addButton(self.close_button, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(button_box)

        # Connect to language change signal and clean up on destruction
        on_language_changed(self.retranslate)
        self.destroyed.connect(lambda cb=self.retranslate: off_language_changed(cb))

        # Add status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_tabs(self) -> None:
        """Build all configuration tabs."""
        # Remember current tab index
        current_tab_index = self.tab_widget.currentIndex()

        # Clear all tabs
        self.tab_widget.clear()

        self.tab_widget.addTab(self.input_tab, t("config_window.tabs.input"))
        self.tab_widget.addTab(self.output_tab, t("config_window.tabs.output"))
        self.tab_widget.addTab(self.general_tab, t("config_window.tabs.general"))

        # Try to restore previous tab index
        if current_tab_index >= 0 and current_tab_index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(current_tab_index)

    def load_settings(self) -> None:
        """Load settings from configuration file."""
        try:
            self.settings = self.config_manager.load_config()
            self.populate_tabs()
            logger.info("Settings loaded successfully")
        except Exception as e:
            QMessageBox.critical(
                self,
                t("config_window.dialogs.error_loading_title"),
                t("config_window.dialogs.error_loading_message", error=str(e)),
            )
            logger.error("Failed to load settings: %s", e)

    def populate_tabs(self) -> None:
        """Populate all tabs with current settings."""
        if not self.settings:
            return

        # Populate tabs
        self.scanner_tab.set_values(self.settings.scanner)
        self.output_tab.set_values(self.settings.output)
        self.logging_tab.set_values(self.settings.logging)
        self.gui_tab.set_values(self.settings.gui)
        self.sav_processing_tab.set_values(self.settings.sav_processing)
        self.clipboard_tab.set_values(self.settings.clipboard)

    def collect_settings(self) -> AppSettings:
        """Collect settings from all tabs.

        The external_tools and database_builder sections are not edited in the
        scanner app (their UI lives in fs_tools), so their values are preserved
        from the currently loaded settings rather than read from a tab.

        Returns:
            AppSettings: AppSettings instance with current values from tabs
        """
        defaults = self.settings or AppSettings()
        return AppSettings(
            scanner=self.scanner_tab.get_values(),
            output=self.output_tab.get_values(),
            external_tools=defaults.external_tools,
            database_builder=defaults.database_builder,
            logging=self.logging_tab.get_values(),
            gui=self.gui_tab.get_values(),
            sav_processing=self.sav_processing_tab.get_values(),
            clipboard=self.clipboard_tab.get_values(),
        )

    def save_settings(self) -> None:
        """Save current settings to configuration file."""
        try:
            # Collect settings from tabs (already validated by Pydantic)
            new_settings = self.collect_settings()

            # Check if the language changed
            language_changed = new_settings.gui.language != self._current_language

            # Save settings
            success, msg = self.config_manager.save_config(new_settings)

            if success:
                self.settings = new_settings
                # Clear the settings cache so new settings take effect
                # Note: dependency caches are cleared when server stops
                reload_settings()

                # Apply language change (this emits signal to retranslate all windows)
                if language_changed:
                    self._current_language = new_settings.gui.language
                    set_language(new_settings.gui.language)

                self.status_bar.showMessage(t("config_window.dialogs.saved_successfully"), 3000)

                logger.info("Settings saved successfully")
            else:
                QMessageBox.critical(
                    self,
                    t("config_window.dialogs.error_saving_title"),
                    msg,
                )
                logger.error("Failed to save settings: %s", msg)

        except Exception as e:
            QMessageBox.critical(
                self,
                t("config_window.dialogs.error_title"),
                t("config_window.dialogs.error_unexpected", error=str(e)),
            )
            logger.error("Unexpected error saving settings: %s", e, exc_info=True)

    def has_changes(self) -> bool:
        """Check if current settings differ from loaded settings.

        Returns:
            bool: True if there are unsaved changes
        """
        if not self.settings:
            return False

        current_settings = self.collect_settings()
        return current_settings != self.settings

    def showEvent(self, event: QShowEvent) -> None:
        """Fit the window height to its content the first time it is shown.

        Args:
            event (QShowEvent): The show event.
        """
        super().showEvent(event)
        if not self._height_fitted:
            self._height_fitted = True
            self._fit_height_to_content()

    def _fit_height_to_content(self) -> None:
        """Resize the height so the tallest tab fits without a scrollbar.

        The non-page chrome (tab bar, hint, buttons, margins) is measured as
        ``window height - page height`` and added to the tallest tab's content
        height hint, so the window adapts to each platform's font/DPI metrics
        and never ends up taller than the content needs.
        """
        page = self.tab_widget.currentWidget()
        if page is None:
            return

        chrome = self.height() - page.height()
        tab_heights = [
            widget.sizeHint().height()
            for i in range(self.tab_widget.count())
            if (widget := self.tab_widget.widget(i)) is not None
        ]
        needed = chrome + max(tab_heights, default=0) + 8

        # Never grow past the available screen height.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            needed = min(needed, screen.availableGeometry().height() - 80)

        self.resize(self.width(), needed)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Handle key press events.

        Args:
            event (QKeyEvent | None): Key press event
        """
        if event is None:
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Handle window close event to check for unsaved changes.

        Args:
            event (QCloseEvent | None): Close event
        """
        should_close = False

        if self.has_changes():
            reply = QMessageBox.question(
                self,
                t("config_window.dialogs.unsaved_changes_title"),
                t("config_window.dialogs.unsaved_changes_message"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )

            if reply == QMessageBox.StandardButton.Save:
                self.save_settings()
                # Only close if save was successful (no more changes)
                should_close = not self.has_changes()
            elif reply == QMessageBox.StandardButton.Discard:
                should_close = True
            # else: Cancel - should_close remains False
        else:
            should_close = True

        if event:
            if should_close:
                event.accept()
                self.closed.emit()
            else:
                event.ignore()

    def retranslate(self, _language: str = "") -> None:
        """Update all translatable strings when language changes.

        Args:
            _language: The new language code (unused, translations fetched via t())
        """
        self.setWindowTitle(t("config_window.title"))
        self.hint_label.setText(t("config_window.tip_hover"))
        self.save_button.setText(t("common.save"))
        self.close_button.setText(t("common.close"))

        # Rebuild tabs with translated names
        self._build_tabs()
