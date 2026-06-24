"""Configuration manager for loading and saving settings."""

import json
import logging
from pathlib import Path

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages loading and saving of application configuration."""

    def __init__(self) -> None:
        """Initialize the configuration manager."""
        self.config_path = Path("~/.fs_config").expanduser()

    def load_config(self) -> AppSettings:
        """Load configuration from file or create default.

        Returns:
            AppSettings: Loaded configuration or default if loading fails.
        """
        try:
            settings = get_settings()
            logger.info("Configuration loaded successfully from %s", self.config_path)
            return settings
        except Exception as e:
            logger.warning("Failed to load config, using defaults: %s", e)
            return AppSettings()

    def save_config(self, settings: AppSettings) -> tuple[bool, str]:
        """Save configuration to file.

        Args:
            settings (AppSettings): AppSettings instance to save.

        Returns:
            tuple[bool, str]: Tuple of (success, message).
        """
        try:
            # Convert settings to dict
            config_dict = settings.model_dump(mode="json", exclude_none=False)

            # Save to file with pretty printing
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            # Clear the settings cache so next load reads from file
            get_settings.cache_clear()

            logger.info("Configuration saved successfully to %s", self.config_path)
            return True, f"Configuration saved to {self.config_path}"

        except Exception as e:
            error_msg = f"Failed to save configuration: {e}"
            logger.error(error_msg)
            return False, error_msg
