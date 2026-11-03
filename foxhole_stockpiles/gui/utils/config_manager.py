"""Configuration manager for loading and saving settings."""

import json
import logging

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.config_path import default_config_path
from foxhole_stockpiles.core.utils import write_private_file

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages loading and saving of application configuration."""

    def __init__(self) -> None:
        """Initialize the configuration manager."""
        self.config_path = default_config_path()

    def load_config(self) -> AppSettings:
        """Load the configuration file.

        A broken file is left to the caller to report. Showing defaults instead would
        let a later save replace it, losing the tokens and URLs it holds.

        Returns:
            AppSettings: The loaded configuration.
        """
        settings = get_settings()
        logger.info("Configuration loaded successfully from %s", self.config_path)
        return settings

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

            # Save to file with pretty printing, restricted to the owner since
            # this config can hold a plaintext webhook auth token.
            write_private_file(
                path=self.config_path,
                content=json.dumps(config_dict, indent=2, ensure_ascii=False),
            )

            # Clear the settings cache so next load reads from file
            get_settings.cache_clear()

            logger.info("Configuration saved successfully to %s", self.config_path)
            return True, f"Configuration saved to {self.config_path}"

        except Exception as e:  # noqa: BLE001 - surface save errors to the user
            logger.error("Failed to save configuration: %s", e)
            return False, f"Failed to save configuration: {e}"
