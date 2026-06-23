"""Clipboard Processing settings tab."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.clipboard import ClipboardSettings
from foxhole_stockpiles.enums.clip_mode import ClipMode
from foxhole_stockpiles.gui.widgets.capture_key_dialog import CaptureKeyDialog
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class ClipboardTab(QWidget):
    """Tab for Clipboard Processing configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the Clipboard Processing tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._clip_capture_key_value: str | None = None
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Clipboard mode (manual hotkey read vs. auto-monitor)
        self.mode_label = QLabel()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("", ClipMode.MANUAL)
        self.mode_combo.addItem("", ClipMode.MONITOR)
        form_layout.addRow(self.mode_label, self.mode_combo)

        # Clipboard hotkey (used in manual mode)
        self.clip_key_label = QLabel()
        clip_key_layout_widget = QWidget()
        clip_key_layout = QHBoxLayout(clip_key_layout_widget)
        clip_key_layout.setContentsMargins(0, 0, 0, 0)
        self.clip_key_display = QLineEdit()
        self.clip_key_display.setReadOnly(True)
        self.clip_key_change = QPushButton()
        self.clip_key_change.clicked.connect(self._change_clip_key)
        self.clip_key_clear = QPushButton()
        self.clip_key_clear.clicked.connect(self._clear_clip_key)
        clip_key_layout.addWidget(self.clip_key_display)
        clip_key_layout.addWidget(self.clip_key_change)
        clip_key_layout.addWidget(self.clip_key_clear)
        form_layout.addRow(self.clip_key_label, clip_key_layout_widget)

        # Poll interval
        self.poll_interval_label = QLabel()
        self.poll_interval_input = QDoubleSpinBox()
        self.poll_interval_input.setRange(0.1, 60.0)
        self.poll_interval_input.setSingleStep(0.5)
        self.poll_interval_input.setDecimals(1)
        self.poll_interval_input.setSuffix(" s")
        form_layout.addRow(self.poll_interval_label, self.poll_interval_input)

        layout.addLayout(form_layout)
        layout.addStretch()

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
        self.mode_label.setText(t("clipboard_tab.mode_label"))
        self.mode_label.setToolTip(t("clipboard_tab.mode_tooltip"))
        self.mode_combo.setItemText(0, t("clipboard_tab.mode_manual"))
        self.mode_combo.setItemText(1, t("clipboard_tab.mode_monitor"))

        self.clip_key_label.setText(t("clipboard_tab.clip_hotkey"))
        self.clip_key_label.setToolTip(t("clipboard_tab.clip_hotkey_tooltip"))
        self.clip_key_display.setPlaceholderText(t("clipboard_tab.clip_hotkey_placeholder"))
        self.clip_key_change.setText(t("clipboard_tab.clip_hotkey_change"))
        self.clip_key_clear.setText(t("common.clear"))

        self.poll_interval_label.setText(t("clipboard_tab.poll_interval_label"))
        self.poll_interval_label.setToolTip(t("clipboard_tab.poll_interval_tooltip"))

    def _change_clip_key(self) -> None:
        """Open the key-capture dialog and store the chosen clipboard hotkey."""
        dialog = CaptureKeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.key_text:
            self._clip_capture_key_value = dialog.key_text
            self.clip_key_display.setText(dialog.key_text)

    def _clear_clip_key(self) -> None:
        """Clear the configured clipboard hotkey."""
        self._clip_capture_key_value = None
        self.clip_key_display.clear()

    def set_values(self, settings: ClipboardSettings) -> None:
        """Set widget values from settings.

        Args:
            settings (ClipboardSettings): ClipboardSettings instance to load
                values from.
        """
        mode_index = self.mode_combo.findData(settings.mode)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        self._clip_capture_key_value = settings.clip_capture_key
        self.clip_key_display.setText(settings.clip_capture_key or "")
        self.poll_interval_input.setValue(settings.poll_interval)

    def get_values(self) -> ClipboardSettings:
        """Get current values from widgets.

        Returns:
            ClipboardSettings: ClipboardSettings instance with current values.
        """
        return ClipboardSettings(
            mode=self.mode_combo.currentData(),
            clip_capture_key=self._clip_capture_key_value or None,
            poll_interval=self.poll_interval_input.value(),
        )
