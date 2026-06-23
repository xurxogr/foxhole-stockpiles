"""GUI settings tab."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.gui import GUISettings
from foxhole_stockpiles.i18n import (
    get_available_languages,
    off_language_changed,
    on_language_changed,
    t,
)


class GUITab(QWidget):
    """Tab for GUI configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the GUI tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Window Behavior Group
        self.window_group = QGroupBox("Window Behavior")
        window_layout = QFormLayout()
        self.window_group.setLayout(window_layout)

        # Minimize to Tray
        self.minimize_label = QLabel("Minimize to Tray:")
        self.minimize_label.setToolTip(
            "When enabled, closing the window minimizes to system tray\n"
            "instead of quitting the application.\n\n"
            "The application will continue running in the background.\n"
            "Right-click the tray icon to access options or quit."
        )
        self.minimize_to_tray_input = QCheckBox("Minimize to tray on close")
        window_layout.addRow(self.minimize_label, self.minimize_to_tray_input)

        layout.addWidget(self.window_group)

        # Language Group
        self.language_group = QGroupBox("Language")
        language_layout = QFormLayout()
        self.language_group.setLayout(language_layout)

        self.language_label = QLabel("Language:")
        self.language_label.setToolTip("Select the language for the GUI.")
        self.language_input = QComboBox()
        # Populate with available languages
        for code, name in get_available_languages():
            self.language_input.addItem(name, code)
        language_layout.addRow(self.language_label, self.language_input)

        layout.addWidget(self.language_group)
        layout.addStretch()

        # Connect to language change events for retranslation
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)

        # Disconnect callback when widget is destroyed
        self.destroyed.connect(self._cleanup)

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event.

        Args:
            _language: The new language code (unused).
        """
        self.retranslate()

    def _cleanup(self) -> None:
        """Clean up signal connections when widget is destroyed."""
        off_language_changed(self._language_callback)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.window_group.setTitle(t("gui_tab.window_behavior_group"))
        self.minimize_label.setText(t("gui_tab.minimize_to_tray"))
        self.minimize_label.setToolTip(t("gui_tab.minimize_tooltip"))
        self.minimize_to_tray_input.setText(t("gui_tab.minimize_checkbox"))

        self.language_group.setTitle(t("gui_tab.language").rstrip(":"))
        self.language_label.setText(t("gui_tab.language"))
        self.language_label.setToolTip(t("gui_tab.language_tooltip"))

    def set_values(self, settings: GUISettings) -> None:
        """Set widget values from settings.

        Args:
            settings (GUISettings): GUISettings instance to load values from.
        """
        # Set minimize to tray
        self.minimize_to_tray_input.setChecked(settings.minimize_to_tray)

        # Set language
        lang_index = self.language_input.findData(settings.language)
        if lang_index >= 0:
            # Block signals to prevent triggering language change during load
            self.language_input.blockSignals(True)
            self.language_input.setCurrentIndex(lang_index)
            self.language_input.blockSignals(False)

    def get_values(self) -> GUISettings:
        """Get current values from widgets.

        Returns:
            GUISettings: GUISettings instance with current values from widgets
        """
        language: str = self.language_input.currentData() or "en"
        return GUISettings(
            minimize_to_tray=self.minimize_to_tray_input.isChecked(),
            language=language,
        )
