"""Qt log handler for capturing logs and emitting them to GUI."""

import logging
from datetime import datetime

from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    """Custom log handler that emits log records as Qt signals."""

    # Identifier to recognize this handler type in logging configuration
    HANDLER_NAME = "foxhole_qt_gui_handler"

    log_message = Signal(dict)

    def __init__(self) -> None:
        """Initialize the Qt log handler."""
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self._is_closed = False
        # Set name to identify this handler
        self.set_name(self.HANDLER_NAME)
        # Prevent logging.shutdown() from trying to flush this handler
        # since Qt may delete the C++ object before Python cleanup
        self.flushOnClose = False

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        """Emit a log record.

        Args:
            record (logging.LogRecord): Log record to emit
        """
        if self._is_closed:
            return

        try:
            # Determine color based on logger name and level
            if "gui" in record.name or "capture" in record.name:
                color = "#00BFFF"  # GUI / capture logs in cyan
            else:
                color = "#FFFFFF"  # Other logs in white

            # Override with level-specific colors
            if record.levelno >= logging.ERROR:
                color = "#FF6B6B"  # Red for errors
            elif record.levelno >= logging.WARNING:
                color = "#FFA500"  # Orange for warnings

            # Emit structured log data
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
                "level": record.levelname,
                "module": record.name,
                "message": record.getMessage(),
                "color": color,
            }
            self.log_message.emit(log_data)
        except (RuntimeError, ValueError, AttributeError):
            # RuntimeError: Qt C++ object deleted
            # ValueError: formatting error
            # AttributeError: signal disconnected
            self.handleError(record)

    def __getattribute__(self, name: str) -> object:
        """Override attribute access to handle Qt object deletion gracefully.

        Args:
            name (str): Attribute name

        Returns:
            object: Attribute value, or default for special attributes if Qt deleted

        Raises:
            AttributeError: If attribute doesn't exist
        """
        try:
            return super().__getattribute__(name)
        except RuntimeError:
            # Qt C++ object has been deleted, return safe defaults
            if name == "flushOnClose":
                return False
            # For other attributes during shutdown, return None
            return None

    def close(self) -> None:
        """Close the handler and mark it as closed to prevent further emissions."""
        self._is_closed = True
        super().close()
