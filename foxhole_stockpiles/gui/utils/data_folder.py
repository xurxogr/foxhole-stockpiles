"""Access to the repository folder where the data files can be downloaded from."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from foxhole_stockpiles.core.constants import DATA_DOWNLOAD_URL


def open_data_folder() -> None:
    """Open the repository data folder in the default browser."""
    QDesktopServices.openUrl(QUrl(DATA_DOWNLOAD_URL))
