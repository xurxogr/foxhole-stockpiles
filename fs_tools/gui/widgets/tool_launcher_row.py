"""Clickable launcher row widget for the fs-tools main window.

Renders a full-width row with an icon, a title and a short description.
The whole row is clickable and emits ``clicked`` on release.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ToolLauncherRow(QFrame):
    """A full-width, clickable launcher entry.

    Displays an icon on the left and a stacked title/description on the
    right. Clicking anywhere on the row emits :attr:`clicked`.
    """

    clicked = Signal()

    _ICON_SIZE = 40

    def __init__(self, icon: QIcon, parent: QWidget | None = None) -> None:
        """Initialize the launcher row.

        Args:
            icon (QIcon): Icon shown on the left of the row.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setObjectName("toolLauncherRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "#toolLauncherRow { border: 1px solid palette(mid); border-radius: 6px; "
            "background: palette(base); }"
            "#toolLauncherRow:hover { background: palette(alternate-base); "
            "border-color: palette(highlight); }"
            "#toolLauncherRow:disabled { background: palette(window); "
            "border-color: palette(midlight); }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        self._icon_label = QLabel()
        self._icon_label.setPixmap(icon.pixmap(self._ICON_SIZE, self._ICON_SIZE))
        self._icon_label.setFixedSize(self._ICON_SIZE, self._ICON_SIZE)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self._title_label = QLabel()
        title_font = self._title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        self._title_label.setFont(title_font)
        self._title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self._title_label)

        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        self._description_label.setStyleSheet("color: gray;")
        self._description_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self._description_label)

        layout.addLayout(text_layout, 1)

    def set_available(self, available: bool) -> None:
        """Enable or disable the row.

        A disabled row is greyed out, shows the default cursor and does not
        emit :attr:`clicked`, so a tool whose required configuration is missing
        cannot be launched.

        Args:
            available (bool): Whether the tool can be launched.
        """
        self.setEnabled(available)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if available else Qt.CursorShape.ArrowCursor
        )

    def set_text(self, title: str, description: str) -> None:
        """Update the row's title and description text.

        Args:
            title (str): The tool name shown in bold.
            description (str): The short explanation shown beneath the title.
        """
        self._title_label.setText(title)
        self._description_label.setText(description)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        """Emit ``clicked`` when the row is released with the left button.

        Args:
            event (QMouseEvent | None): The mouse release event.
        """
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)
