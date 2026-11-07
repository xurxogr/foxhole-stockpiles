"""A button that lists the placeholders a field accepts."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QToolTip, QWidget

from foxhole_stockpiles.i18n import t

_HELP_KEY = "output_tab.handler_dialog.placeholder_help"


class PlaceholderHelpButton(QToolButton):
    """A "?" beside a field with placeholders.

    The list shows on hover, as any tooltip, and on a click too, since a label
    nobody hovers was where it used to hide.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the button.

        Args:
            parent (QWidget | None): Its parent widget.
        """
        super().__init__(parent)
        self.setText("?")
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.clicked.connect(self._show_help)
        self.retranslate()

    def retranslate(self) -> None:
        """Update the list in the language of the window."""
        self.setToolTip(t(_HELP_KEY))
        self.setAccessibleName(t(f"{_HELP_KEY}_name"))

    def _show_help(self) -> None:
        """Show the list under the button."""
        QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self.toolTip(), self)
