"""Qt application entry points for the fs-tools desktop application."""

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from foxhole_stockpiles import __version__
from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.i18n import get_translator, set_translations_resource

logger = logging.getLogger(__name__)

__all__ = ["run_debug_viewer", "run_gui", "run_visualizer"]


def _bootstrap() -> QApplication:
    """Initialize logging, translations and the Qt application.

    Returns:
        QApplication: The (possibly pre-existing) Qt application instance.
    """
    language = "en"
    try:
        settings = AppSettings()
        setup_logging(settings.logging)
        language = settings.gui.language
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logger.warning("Could not load settings: %s", e)

    set_translations_resource("fs_tools/i18n/translations")
    get_translator(language)

    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    app.setApplicationName("FS Tools")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("FS")
    return app


def run_gui() -> None:
    """Launch the fs-tools launcher window."""
    from fs_tools.gui.main_window import ToolsMainWindow

    app = _bootstrap()
    window = ToolsMainWindow()
    window.show()
    sys.exit(app.exec())


def run_visualizer(database: Path | None = None) -> None:
    """Open the database visualizer as a standalone window.

    Args:
        database (Path | None): Path to the template database to open.
    """
    from fs_tools.gui.windows.database_visualizer_window import DatabaseVisualizerWindow

    app = _bootstrap()
    window = DatabaseVisualizerWindow(
        parent=None,
        database_path=str(database) if database else None,
    )
    window.show()
    sys.exit(app.exec())


def run_debug_viewer(image: Path, database: Path) -> None:
    """Open the debug image viewer as a standalone window.

    Args:
        image (Path): Screenshot to inspect.
        database (Path): Path to the template database.
    """
    from fs_tools.gui.windows.debug_image_window import DebugImageWindow

    app = _bootstrap()
    window = DebugImageWindow(parent=None, database_path=str(database))
    if hasattr(window, "load_image"):
        window.load_image(str(image))
    window.show()
    sys.exit(app.exec())
