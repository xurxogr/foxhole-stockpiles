"""General settings tab grouping interface and logging options.

Composes the existing GUI and Logging tabs into one "General" tab. The GUI
settings (minimize-to-tray, then language) come first; logging is at the
bottom. The sub-tabs keep their own ``set_values``/``get_values`` and settings
sections; this widget only arranges them.
"""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from foxhole_stockpiles.gui.widgets.config_tabs.gui_tab import GUITab
from foxhole_stockpiles.gui.widgets.config_tabs.logging_tab import LoggingTab
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class GeneralTab(QWidget):
    """Tab grouping the interface (GUI) and logging settings."""

    def __init__(
        self,
        gui_tab: GUITab,
        logging_tab: LoggingTab,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the General tab from the GUI and Logging sub-tabs.

        Args:
            gui_tab (GUITab): The interface settings sub-tab (its own group boxes
                already cover minimize-to-tray and language).
            logging_tab (LoggingTab): The logging settings sub-tab.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._logging_group = QGroupBox()
        self.init_ui(gui_tab, logging_tab)

    def init_ui(self, gui_tab: GUITab, logging_tab: LoggingTab) -> None:
        """Build the layout: interface options first, logging at the bottom.

        Args:
            gui_tab (GUITab): The interface settings sub-tab.
            logging_tab (LoggingTab): The logging settings sub-tab.
        """
        layout = QVBoxLayout(self)

        # GUI sub-tab first (minimize-to-tray and language, each in its own
        # group box already).
        layout.addWidget(gui_tab)

        # Logging at the bottom, filling the remaining space.
        logging_layout = QVBoxLayout(self._logging_group)
        logging_layout.setContentsMargins(8, 4, 8, 4)
        logging_layout.addWidget(logging_tab)
        layout.addWidget(self._logging_group, 1)

        self.retranslate()

        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update the logging group title (sub-tabs retranslate themselves)."""
        self._logging_group.setTitle(t("config_window.tabs.logging"))
