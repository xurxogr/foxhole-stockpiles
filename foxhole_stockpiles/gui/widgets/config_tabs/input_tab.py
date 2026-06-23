"""Input settings tab grouping the three input sources.

Composes the existing Scanner (OCR), SAV, and Clipboard tabs into a single
"Input" tab, each inside a titled group box. The sub-tabs keep their own
``set_values``/``get_values`` and own settings sections; this widget only
arranges them. Nothing here scrolls.
"""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from foxhole_stockpiles.gui.widgets.config_tabs.clipboard_tab import ClipboardTab
from foxhole_stockpiles.gui.widgets.config_tabs.sav_processing_tab import SavProcessingTab
from foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab import ScannerTab
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class InputTab(QWidget):
    """Tab grouping the Scanner (OCR), SAV, and Clipboard input sources."""

    def __init__(
        self,
        scanner_tab: ScannerTab,
        sav_tab: SavProcessingTab,
        clipboard_tab: ClipboardTab,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the Input tab from the three input-source sub-tabs.

        Args:
            scanner_tab (ScannerTab): The screenshot/OCR settings sub-tab.
            sav_tab (SavProcessingTab): The SAV file settings sub-tab.
            clipboard_tab (ClipboardTab): The clipboard settings sub-tab.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._scanner_group = QGroupBox()
        self._sav_group = QGroupBox()
        self._clipboard_group = QGroupBox()
        self.init_ui(scanner_tab, sav_tab, clipboard_tab)

    def init_ui(
        self,
        scanner_tab: ScannerTab,
        sav_tab: SavProcessingTab,
        clipboard_tab: ClipboardTab,
    ) -> None:
        """Build the layout: one group box per input source, stacked.

        Args:
            scanner_tab (ScannerTab): The screenshot/OCR settings sub-tab.
            sav_tab (SavProcessingTab): The SAV file settings sub-tab.
            clipboard_tab (ClipboardTab): The clipboard settings sub-tab.
        """
        layout = QVBoxLayout(self)
        for group, sub_tab in (
            (self._scanner_group, scanner_tab),
            (self._sav_group, sav_tab),
            (self._clipboard_group, clipboard_tab),
        ):
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(8, 4, 8, 4)
            group_layout.addWidget(sub_tab)
            layout.addWidget(group)
        layout.addStretch()

        self.retranslate()

        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update the group box titles (sub-tabs retranslate themselves)."""
        self._scanner_group.setTitle(t("config_window.tabs.scanner"))
        self._sav_group.setTitle(t("config_window.tabs.sav_processing"))
        self._clipboard_group.setTitle(t("config_window.tabs.clipboard"))
