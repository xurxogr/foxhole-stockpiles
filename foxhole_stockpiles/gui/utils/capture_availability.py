"""Pure settings-availability checks shared by the capture panel's controls."""

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.utils import auto_detect_savefile


def catalog_available(settings: AppSettings) -> bool:
    """Return whether a usable item catalog file is configured.

    Args:
        settings (AppSettings): The settings to read the catalog path from.

    Returns:
        bool: True if a catalog file is configured and exists.
    """
    catalog_path = settings.database_builder.catalog_file
    return bool(catalog_path and catalog_path.exists())


def sav_file_available(settings: AppSettings) -> bool:
    """Return whether a .sav file is configured-and-exists or auto-detectable.

    Args:
        settings (AppSettings): The settings to read the .sav path from.

    Returns:
        bool: True if a usable .sav file path is available.
    """
    path = settings.sav_processing.sav_file_path or auto_detect_savefile()
    return bool(path and path.exists())
