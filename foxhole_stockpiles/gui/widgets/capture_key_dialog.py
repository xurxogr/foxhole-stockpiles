"""Modal dialog that captures the next key press as a hotkey name.

Shared by the config tabs that let the user bind a global hotkey (screenshot
capture, SAV scan).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from foxhole_stockpiles.i18n import t

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
}


class CaptureKeyDialog(QDialog):
    """Modal dialog that captures the next key press as a hotkey name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the key capture dialog.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.key_text: str | None = None
        self.setWindowTitle(t("scanner_tab.press_key_title"))
        self.setModal(True)
        self.setMinimumSize(400, 170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self._label = QLabel(t("scanner_tab.press_key_prompt"))
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); border-radius: 6px; padding: 18px; }"
        )
        layout.addWidget(self._label)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Capture the pressed key combination and close the dialog.

        Args:
            event (QKeyEvent | None): The key press event.
        """
        if event is None:
            return

        key = Qt.Key(event.key())
        if key in _MODIFIER_KEYS:
            return  # wait for a non-modifier key, keeping modifiers held
        if key == Qt.Key.Key_Escape:
            self.reject()
            return

        # keyCombination() preserves held modifiers (e.g. Ctrl+F3), unlike the
        # bare key, so combinations are captured rather than just the base key.
        self.key_text = QKeySequence(event.keyCombination()).toString(
            QKeySequence.SequenceFormat.PortableText
        )
        self.accept()
