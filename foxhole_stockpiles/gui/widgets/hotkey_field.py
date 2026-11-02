"""Form field that shows a global hotkey with change and clear buttons."""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from foxhole_stockpiles.gui.widgets.capture_key_dialog import CaptureKeyDialog
from foxhole_stockpiles.i18n import t


class HotkeyField(QWidget):
    """Read-only hotkey display with buttons to capture a new key or clear it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the hotkey field.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._key: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.change_button = QPushButton()
        self.change_button.clicked.connect(self.change)
        self.clear_button = QPushButton()
        self.clear_button.clicked.connect(self.clear)
        layout.addWidget(self.display)
        layout.addWidget(self.change_button)
        layout.addWidget(self.clear_button)

    def key(self) -> str | None:
        """Return the configured hotkey.

        Returns:
            str | None: The hotkey, or None when none is configured.
        """
        return self._key or None

    def set_key(self, key: str | None) -> None:
        """Show the given hotkey.

        Args:
            key (str | None): The hotkey to show, or None for no hotkey.
        """
        self._key = key
        self.display.setText(key or "")

    def change(self) -> None:
        """Open the key-capture dialog and store the chosen hotkey."""
        dialog = CaptureKeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.key_text:
            self.set_key(dialog.key_text)

    def clear(self) -> None:
        """Clear the configured hotkey."""
        self.set_key(None)

    def retranslate(self, placeholder: str, change_text: str) -> None:
        """Update the translatable strings.

        Args:
            placeholder (str): Text shown while no hotkey is configured.
            change_text (str): Label of the change button.
        """
        self.display.setPlaceholderText(placeholder)
        self.change_button.setText(change_text)
        self.clear_button.setText(t("common.clear"))
