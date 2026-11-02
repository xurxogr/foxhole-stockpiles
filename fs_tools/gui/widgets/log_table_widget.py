"""Table widget that shows process log entries and copies them on Ctrl+C."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from foxhole_stockpiles.i18n import t


class LogTableWidget(QTableWidget):
    """Read-only, four-column table of time, level, module and message."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the log table.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setColumnCount(4)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setWordWrap(True)
        vertical_header = self.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)
            vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.setStyleSheet("QTableWidget { background-color: #1E1E1E; gridline-color: #3E3E3E; }")

        header = self.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.setColumnWidth(0, 150)
        self.setColumnWidth(1, 80)
        self.setColumnWidth(2, 250)

    def retranslate(self) -> None:
        """Update the column headers to the current language."""
        self.setHorizontalHeaderLabels(
            [
                t("common.log_columns.time"),
                t("common.log_columns.level"),
                t("common.log_columns.module"),
                t("common.log_columns.message"),
            ]
        )

    def append_log(self, log_data: dict[str, str]) -> None:
        """Append a log entry and scroll to it.

        Args:
            log_data (dict[str, str]): The entry's timestamp, level, module, message and color.
        """
        row_position = self.rowCount()
        self.insertRow(row_position)

        brush = QBrush(QColor(log_data["color"]))

        time_item = QTableWidgetItem(log_data["timestamp"])
        time_item.setForeground(brush)

        level_item = QTableWidgetItem(log_data["level"])
        level_item.setForeground(brush)

        module_item = QTableWidgetItem(log_data["module"])
        module_item.setForeground(brush)

        message_item = QTableWidgetItem(log_data["message"])
        message_item.setForeground(brush)
        message_item.setTextAlignment(int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop))

        self.setItem(row_position, 0, time_item)
        self.setItem(row_position, 1, level_item)
        self.setItem(row_position, 2, module_item)
        self.setItem(row_position, 3, message_item)

        self.resizeRowToContents(row_position)
        self.scrollToBottom()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Copy the selected rows on the copy shortcut, otherwise handle the key normally.

        Args:
            event (QKeyEvent | None): The key event.
        """
        if not event:
            return

        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selected_logs()
        else:
            super().keyPressEvent(event)

    def _copy_selected_logs(self) -> None:
        """Copy the selected rows to the clipboard, one line per row."""
        selection_model = self.selectionModel()
        if not selection_model:
            return

        selected_indexes = selection_model.selectedRows()
        if not selected_indexes:
            return

        lines = []
        for index in sorted(selected_indexes, key=lambda x: x.row()):
            row = index.row()
            time_item = self.item(row, 0)
            level_item = self.item(row, 1)
            module_item = self.item(row, 2)
            message_item = self.item(row, 3)

            if time_item and level_item and module_item and message_item:
                line = (
                    f"[{time_item.text()}] {level_item.text()} "
                    f"{module_item.text()}: {message_item.text()}"
                )
                lines.append(line)

        if lines:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText("\n".join(lines))
