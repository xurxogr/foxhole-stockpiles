"""Base of the windows that run a long process and show its logs."""

import logging
from datetime import datetime

from PySide6.QtWidgets import QGroupBox, QMainWindow, QVBoxLayout, QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler
from fs_tools.gui.widgets.log_table_widget import LogTableWidget

_COLOR_SUCCESS = "#00FF00"
_COLOR_INFO = "#2196F3"
_COLOR_WARNING = "#FFA500"
_COLOR_ERROR = "#FF0000"


class ProcessLogWindow(QMainWindow):
    """Window showing the application logs while its process runs.

    The subclass places ``logs_group`` in its layout and sets its title.
    """

    def __init__(
        self, settings: AppSettings, log_module: str, parent: QWidget | None = None
    ) -> None:
        """Initialize the log display and its handler.

        Args:
            settings (AppSettings): The settings the window works with.
            log_module (str): Module shown in the messages of the process.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.settings = settings
        self._log_module = log_module
        self._log_level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)

        self.log_display = LogTableWidget()
        self.logs_group = QGroupBox()
        logs_layout = QVBoxLayout()
        logs_layout.addWidget(self.log_display)
        self.logs_group.setLayout(logs_layout)

        self.log_handler = QtLogHandler()
        self.log_handler.setLevel(self._log_level)
        self.log_handler.log_message.connect(self.log_display.append_log)

    def start_log_capture(self) -> None:
        """Show the application logs from now on, at the configured level."""
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(self._log_level)

    def stop_log_capture(self) -> None:
        """Stop showing the application logs; the handler is reused by the next process."""
        logging.getLogger().removeHandler(self.log_handler)

    def clear_logs(self) -> None:
        """Clear the log display."""
        self.log_display.setRowCount(0)

    def log_success(self, message: str) -> None:
        """Show that the process succeeded.

        Args:
            message (str): The message.
        """
        self._add_row(level="INFO", message=message, color=_COLOR_SUCCESS)

    def log_info(self, message: str) -> None:
        """Show the progress of the process.

        Args:
            message (str): The message.
        """
        self._add_row(level="INFO", message=message, color=_COLOR_INFO)

    def log_warning(self, message: str) -> None:
        """Show that the process did not complete.

        Args:
            message (str): The message.
        """
        self._add_row(level="WARNING", message=message, color=_COLOR_WARNING)

    def log_error(self, message: str) -> None:
        """Show an error of the process.

        Args:
            message (str): The message.
        """
        self._add_row(level="ERROR", message=message, color=_COLOR_ERROR)

    def _add_row(self, level: str, message: str, color: str) -> None:
        """Add a message of the process to the display.

        Args:
            level (str): The level shown.
            message (str): The message.
            color (str): The color of the row.
        """
        self.log_display.append_log(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": level,
                "module": self._log_module,
                "message": message,
                "color": color,
            }
        )

    def _cleanup_and_accept(self, event: object) -> None:
        """Close the log handler, preventing further emissions, and accept the close event.

        Args:
            event (object): Close event
        """
        self.log_handler.close()
        event.accept()  # type: ignore[attr-defined]
