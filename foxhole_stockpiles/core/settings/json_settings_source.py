"""Custom pydantic-settings sources for configuration loading."""

import json
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from pydantic_settings import JsonConfigSettingsSource

from foxhole_stockpiles.core.settings.config_migrator import ConfigMigrator


class Utf8JsonConfigSettingsSource(JsonConfigSettingsSource):
    """JSON config settings source that reads files with UTF-8 encoding.

    Migrations are applied here because pydantic-settings validates each
    source's data before the model_validator runs. Old config keys like
    'output_format' would trigger validation errors otherwise.
    """

    def _read_file(self, file_path: Path | Traversable) -> dict[str, Any]:
        """Read and parse a JSON file with UTF-8 encoding.

        Args:
            file_path (Path | Traversable): Path to the JSON file.

        Returns:
            dict[str, Any]: The parsed JSON data with migrations applied
        """
        with file_path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return ConfigMigrator.apply_migrations(data)
