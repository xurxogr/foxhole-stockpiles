"""Catalog service for loading and querying item catalog data."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CatalogEntry(BaseModel):
    """Catalog entry with item code and display name."""

    code: str
    display_name: str


class CatalogService:
    """Service for loading and querying item catalog data.

    Provides code-to-display-name lookups for the web interface.
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
                    self._catalog[code] = CatalogEntry(code=code, display_name=display_name)

            logger.info("Loaded %d items from catalog", len(self._catalog))

        except json.JSONDecodeError as e:
            logger.error("Failed to parse catalog file %s: %s", self._catalog_path, e)
        except Exception as e:
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

    def get_entry(self, code: str) -> CatalogEntry | None:
        """Get full catalog entry for an item code.

        Args:
            code: The item code to look up.

        Returns:
            The CatalogEntry if found, otherwise None.
        """
        self._load()
        return self._catalog.get(code)

    def is_loaded(self) -> bool:
        """Check if the catalog has been loaded.

        Returns:
            True if catalog has been loaded (even if empty).
        """
        return self._loaded

    @property
    def item_count(self) -> int:
        """Get the number of items in the catalog.

        Returns:
            Number of catalog entries loaded.
        """
        self._load()
        return len(self._catalog)


@lru_cache
def get_catalog_service() -> CatalogService:
    """Get a process-wide cached catalog service built from current settings.

    Returns:
        CatalogService: A catalog service using the configured catalog file.
    """
    from foxhole_stockpiles.core.settings import get_settings

    catalog_path = get_settings().database_builder.catalog_file
    return CatalogService(catalog_path=catalog_path)
