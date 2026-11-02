"""Configuration module for the app."""

import logging
from functools import lru_cache

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.json_settings_source import Utf8JsonConfigSettingsSource

logger = logging.getLogger(__name__)


@lru_cache
def get_settings() -> AppSettings:
    """Get the settings.

    Returns:
        AppSettings: The settings
    """
    return AppSettings()


def reload_settings() -> AppSettings:
    """Reload the settings by clearing the cache.

    Always reconfigures logging to ensure changes take effect.

    Returns:
        AppSettings: Newly loaded settings
    """
    # Clear cache and get new settings
    get_settings.cache_clear()
    new_settings = get_settings()

    # Always reconfigure logging to ensure any changes take effect
    setup_logging(new_settings.logging)

    return new_settings


__all__ = [
    "AppSettings",
    "Utf8JsonConfigSettingsSource",
    "get_settings",
    "reload_settings",
]
