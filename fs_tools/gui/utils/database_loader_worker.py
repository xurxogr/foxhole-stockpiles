"""Background worker that loads every resolution of a template database."""

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from fs_tools.core.template_store import read_all_resolutions

logger = logging.getLogger(__name__)


class DatabaseLoaderWorker(QThread):
    """Thread for loading all databases in background."""

    databases_loaded = Signal(object)  # dict[SupportedResolution, list[IconTemplate]]
    error = Signal(str)

    def __init__(self, database_path: str) -> None:
        """Initialize the database loader.

        Args:
            database_path (str): Path to the database file to load.
        """
        super().__init__()
        self.database_path = database_path

    def run(self) -> None:
        """Load all databases in background thread.

        Emits:
            databases_loaded: Signal with loaded databases on success.
            error: Signal with error message on failure.
        """
        try:
            self.databases_loaded.emit(read_all_resolutions(Path(self.database_path)))
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            logger.exception("Failed to load databases")
            self.error.emit(str(e))
