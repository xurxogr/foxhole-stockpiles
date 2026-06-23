"""Utility functions used only by the fs_tools tooling.

Catalog loading, external-tool path validation and perceptual-hash
computation are needed by the catalog/template-database builders, not by the
desktop runtime, so they live here rather than in ``foxhole_stockpiles``.
"""

import json
import logging
import sys
from pathlib import Path

from foxhole_stockpiles.models.catalog_item import CatalogItem


def validate_tool_path(path: Path) -> None:
    """Validate an external tool path for safe subprocess execution.

    Checks that the path:
    - Exists and is a file
    - Does not contain command injection characters
    - Has valid executable extension on Windows

    Args:
        path (Path): Path to the external tool

    Raises:
        ValueError: If the path is invalid or contains suspicious characters
        FileNotFoundError: If the tool does not exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Tool not found: {path}")

    if not path.is_file():
        raise ValueError(f"Tool path is not a file: {path}")

    # Check for command injection characters in the resolved path
    path_str = str(path.resolve())
    dangerous_chars = [";", "|", "&", "\n", "\r", "`", "$", "(", ")", "{", "}"]
    for char in dangerous_chars:
        if char in path_str:
            raise ValueError(f"Invalid character '{char}' in tool path: {path}")

    # On Windows, verify executable extension
    if sys.platform == "win32":
        valid_extensions = {".exe", ".bat", ".cmd", ".com"}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(
                f"Invalid executable extension '{path.suffix}' for Windows tool: {path}"
            )


def load_catalog(path: Path) -> list[CatalogItem]:
    """Load catalog.json file with item definitions.

    Args:
        path (Path): Path to the catalog.json file.

    Returns:
        list[CatalogItem]: List of CatalogItem instances loaded from the file.
    """
    logger = logging.getLogger(__name__)
    if not path.exists():
        logger.warning("Catalog file not found at %s", path)
        return []

    catalog_data = []
    try:
        with path.open(encoding="utf-8") as f:
            catalog_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse catalog file %s: %s", path, e)
        return []

    items = [CatalogItem.from_catalog(item=item) for item in catalog_data]
    valid_items = [item for item in items if item is not None]

    if len(valid_items) != len(catalog_data):
        failed_count = len(catalog_data) - len(valid_items)
        logger.warning(
            "Failed to convert %d out of %d catalog items", failed_count, len(catalog_data)
        )

    return valid_items
