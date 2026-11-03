"""The download buttons of the configuration all open the same place."""

from unittest.mock import patch

from PySide6.QtCore import QUrl

from foxhole_stockpiles.core.constants import DATA_DOWNLOAD_URL
from foxhole_stockpiles.gui.utils.data_folder import open_data_folder


def test_opens_the_data_folder_in_the_browser() -> None:
    """The system browser is asked to open the repository data folder."""
    with patch("foxhole_stockpiles.gui.utils.data_folder.QDesktopServices") as services:
        open_data_folder()

    services.openUrl.assert_called_once_with(QUrl(DATA_DOWNLOAD_URL))
