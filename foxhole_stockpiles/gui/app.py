"""Qt application launcher."""

import logging
import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

from foxhole_stockpiles import __version__
from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.gui.windows.main_window import MainWindow
from foxhole_stockpiles.i18n import get_translator

logger = logging.getLogger(__name__)


def _load_language_from_settings() -> str:
    """Load language setting from config file.

    Returns:
        str: Language code (defaults to 'en' if not found)
    """
    try:
        settings = AppSettings()
        return settings.gui.language
    except Exception as e:  # noqa: BLE001 - fall back to English if settings fail to load
        logger.debug("Could not load language from settings: %s", e)
        return "en"


def launch_gui() -> None:
    """Launch the PySide6 GUI application."""
    # Required for multiprocessing to work correctly in frozen executables (PyInstaller)
    # This must be called before any other multiprocessing code runs
    multiprocessing.freeze_support()

    # Initialize logging from settings
    try:
        settings = AppSettings()
        setup_logging(settings.logging)
    except Exception as e:  # noqa: BLE001 - fall back to basic logging if settings fail to load
        # If settings fail to load, use basic logging config
        logging.basicConfig(level=logging.INFO)
        logger.warning("Could not load settings for logging: %s", e)

    # Initialize translator with user's language preference
    language = _load_language_from_settings()
    get_translator(language)

    app = QApplication(sys.argv)
    app.setApplicationName("FS")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("FS")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
