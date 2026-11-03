"""Rotating file logging handler whose files only their owner can read."""

from logging.handlers import TimedRotatingFileHandler
from typing import TextIO

from foxhole_stockpiles.core.private_log_file import open_private_log


class PrivateRotatingFileHandler(TimedRotatingFileHandler):
    """A ``TimedRotatingFileHandler`` that keeps its log files private.

    A rotation renames the current file, which keeps its mode, and opens a new one
    through ``_open``.
    """

    def _open(self) -> TextIO:  # type: ignore[override]
        """Open the log file.

        Returns:
            TextIO: The open stream.
        """
        return open_private_log(
            path=self.baseFilename, mode=self.mode, encoding=self.encoding, errors=self.errors
        )
