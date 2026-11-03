"""File logging handler whose file only its owner can read."""

import logging
from typing import TextIO

from foxhole_stockpiles.core.private_log_file import open_private_log


class PrivateFileHandler(logging.FileHandler):
    """A ``FileHandler`` that keeps its log file private."""

    def _open(self) -> TextIO:  # type: ignore[override]
        """Open the log file.

        Returns:
            TextIO: The open stream.
        """
        return open_private_log(
            path=self.baseFilename, mode=self.mode, encoding=self.encoding, errors=self.errors
        )
