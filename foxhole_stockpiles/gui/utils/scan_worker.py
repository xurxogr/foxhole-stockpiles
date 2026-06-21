"""Worker thread for scanning screenshots in background."""

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.gui.utils.scanner_client import ScannerClient


class ScanWorker(QThread):
    """Worker thread for scanning screenshots.

    Note: the completion signal is named ``scan_finished`` (not ``finished``) to
    avoid shadowing ``QThread``'s built-in ``finished`` signal, which would cause
    connected slots to fire twice.
    """

    scan_finished = Signal()

    def __init__(self, scanner_client: ScannerClient, filepath: str) -> None:
        """Initialize the scan worker.

        Args:
            scanner_client (ScannerClient): Scanner client instance
            filepath (str): Path to the screenshot file
        """
        super().__init__()
        self.scanner_client = scanner_client
        self.filepath = filepath

    def run(self) -> None:
        """Run the scan in background thread."""
        self.scanner_client.scan_screenshot(self.filepath)
        self.scan_finished.emit()
