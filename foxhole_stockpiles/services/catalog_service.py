"""Catalog service for loading and querying item catalog data."""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from foxhole_stockpiles.core.settings import get_settings

logger = logging.getLogger(__name__)

# Unreal writes enum values as "EItemCategory::SmallArms".
_ENUM_SEPARATOR = "::"
_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _read_category(item: dict[str, Any]) -> str | None:
    """Read the label an item is grouped under.

    Args:
        item (dict[str, Any]): One catalog entry.

    Returns:
        str | None: The item category in readable words, the stockpile category of
            what has none (vehicles and structures), or None in an older catalog.
    """
    item_category = item.get("ItemCategory")
    if isinstance(item_category, str) and item_category:
        return _WORD_BOUNDARY.sub(" ", item_category.rsplit(_ENUM_SEPARATOR, maxsplit=1)[-1])
    stockpile_category = item.get("StockpileCategory")
    return stockpile_category if isinstance(stockpile_category, str) else None


class CatalogEntry(BaseModel):
    """Catalog entry with item code, display name and category."""

    code: str
    display_name: str
    category: str | None = None


class CatalogService:
    """Service for loading and querying item catalog data.

    Provides lookups from a code to its display name and category.
    """

    def __init__(self, catalog_path: Path | None = None) -> None:
        """Initialize the catalog service.

        Args:
            catalog_path: Path to the catalog.json file. If None, lookups will return codes.
        """
        self._catalog_path = catalog_path
        self._catalog: dict[str, CatalogEntry] = {}
        self._loaded = False

    def _load(self) -> None:
        """Load catalog from file. Called lazily on first access."""
        if self._loaded:
            return

        self._loaded = True

        if not self._catalog_path:
            logger.debug("No catalog path configured, display names will use codes")
            return

        if not self._catalog_path.exists():
            logger.warning("Catalog file not found at %s", self._catalog_path)
            return

        try:
            with self._catalog_path.open(encoding="utf-8") as f:
                catalog_data = json.load(f)

            for item in catalog_data:
                code = item.get("CodeName")
                display_name = item.get("DisplayName", code)
                if code:
                    self._catalog[code] = CatalogEntry(
                        code=code, display_name=display_name, category=_read_category(item)
                    )

            logger.info("Loaded %d items from catalog", len(self._catalog))

        except json.JSONDecodeError as e:
            logger.error("Failed to parse catalog file %s: %s", self._catalog_path, e)
        except Exception as e:  # noqa: BLE001 - keep the app usable with an empty catalog
            logger.error("Failed to load catalog: %s", e)

    def get_display_name(self, code: str) -> str:
        """Get display name for an item code.

        Args:
            code: The item code to look up.

        Returns:
            The display name if found, otherwise returns the code itself.
        """
        self._load()
        entry = self._catalog.get(code)
        return entry.display_name if entry else code

    def get_category(self, code: str) -> str | None:
        """Get the category an item is grouped under.

        Args:
            code (str): The item code to look up.

        Returns:
            str | None: The category, or None if the catalog has none for that code.
        """
        self._load()
        entry = self._catalog.get(code)
        return entry.category if entry else None


@lru_cache
def get_catalog_service() -> CatalogService:
    """Get a process-wide cached catalog service built from current settings.

    Returns:
        CatalogService: A catalog service using the configured catalog file.
    """
    catalog_path = get_settings().database_builder.catalog_file
    return CatalogService(catalog_path=catalog_path)
