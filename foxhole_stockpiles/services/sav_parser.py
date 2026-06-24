"""SAV file parsing using fs-sav (Rust implementation).

This module provides a thin wrapper around the fs-sav library,
converting its output to internal Stockpile models.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fs_sav

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem

logger = logging.getLogger(__name__)


def parse_save(
    path: Path | str,
    *,
    public: bool = False,
    reserves: bool = False,
    hex_filter: str | None = None,
    stockpile_type: str | None = None,
    with_items: bool = False,
) -> list[Stockpile]:
    """Parse a .sav file and return Stockpile models.

    Args:
        path (Path | str): Path to the .sav file.
        public (bool): Only return public stockpiles (non-reserve).
        reserves (bool): Only return reserve stockpiles.
        hex_filter (str | None): Filter by hex name.
        stockpile_type (str | None): Filter by stockpile type.
        with_items (bool): Only return stockpiles with items.

    Returns:
        list[Stockpile]: List of parsed stockpiles.

    Raises:
        RuntimeError: If parsing fails.
    """
    raw_stockpiles = fs_sav.parse_save(
        str(path),
        public=public,
        reserves=reserves,
        hex=hex_filter,
        stockpile_type=stockpile_type,
        with_items=with_items,
    )

    if not isinstance(raw_stockpiles, list):
        raise RuntimeError(f"fs_sav.parse_save returned unexpected type: {type(raw_stockpiles)}")

    return [_convert_to_stockpile(s) for s in raw_stockpiles]


def parse_save_bytes(
    data: bytes,
    *,
    public: bool = False,
    reserves: bool = False,
    hex_filter: str | None = None,
    stockpile_type: str | None = None,
    with_items: bool = False,
) -> list[Stockpile]:
    """Parse .sav data from bytes and return Stockpile models.

    Args:
        data (bytes): Raw .sav file bytes.
        public (bool): Only return public stockpiles (non-reserve).
        reserves (bool): Only return reserve stockpiles.
        hex_filter (str | None): Filter by hex name.
        stockpile_type (str | None): Filter by stockpile type.
        with_items (bool): Only return stockpiles with items.

    Returns:
        list[Stockpile]: List of parsed stockpiles.

    Raises:
        RuntimeError: If parsing fails.
    """
    raw_stockpiles = fs_sav.parse_save_bytes(
        data,
        public=public,
        reserves=reserves,
        hex=hex_filter,
        stockpile_type=stockpile_type,
        with_items=with_items,
    )

    if not isinstance(raw_stockpiles, list):
        raise RuntimeError(
            f"fs_sav.parse_save_bytes returned unexpected type: {type(raw_stockpiles)}"
        )

    return [_convert_to_stockpile(s) for s in raw_stockpiles]


def info() -> dict[str, str]:
    """Get parser info.

    Returns:
        dict[str, str]: Parser implementation and version info.
    """
    result: dict[str, str] = fs_sav.info()
    return result


def _convert_to_stockpile(data: dict[str, Any]) -> Stockpile:
    """Convert fs-sav output dict to Stockpile model.

    Args:
        data (dict[str, Any]): Raw stockpile data from fs-sav.

    Returns:
        Stockpile: Converted stockpile model.
    """
    # fs-sav emits canonical in-game CodeNames; pass them through verbatim so a
    # newly-added type is preserved instead of collapsing to "Undefined".
    stockpile_type = data.get("type", "Undefined")

    # Parse coordinates
    coords_data = data.get("coords")
    coords = None
    if coords_data:
        coords = StockpileCoords(
            x=coords_data.get("x", 0.0),
            y=coords_data.get("y", 0.0),
        )

    # Parse items
    items = [
        StockpileItem(
            code=item.get("code", "Unknown"),
            quantity=item.get("quantity", 0),
            crated=item.get("crated", False),
            confidence=None,  # Save file data is exact, no confidence needed
        )
        for item in data.get("items", [])
    ]

    # Parse timestamp
    timestamp_str = data.get("timestamp", "")
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        timestamp = datetime.now(tz=UTC)

    return Stockpile(
        name=data.get("name", ""),
        type=stockpile_type,
        faction=ItemFaction.parse_optional(data.get("faction")),
        hex=data.get("hex"),
        coords=coords,
        is_reserve=data.get("is_reserve", False),
        items=items,
        timestamp=timestamp,
        raw_timestamp=None,  # fs-sav doesn't expose raw ticks
    )
