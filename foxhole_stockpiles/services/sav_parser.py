"""SAV file parsing using fs-sav (Rust implementation).

This module provides a thin wrapper around the fs-sav library,
converting its output to internal Stockpile models.
"""

import logging
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fs_sav
from pydantic import ValidationError

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.factory_order import FactoryOrder
from foxhole_stockpiles.models.refinery import Refinery
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.models.stockpile_tech import StockpileTech

logger = logging.getLogger(__name__)

# Text of the fs-sav error raised when the game kept writing the file while it was read.
_FILE_BUSY_MARKER = "kept changing while being read"

# Fields that only some structure types can hold.
_TYPE_SPECIFIC_FIELDS = frozenset({"tech", "refinery", "factory_orders"})

# What converting unexpected fs-sav data can raise (ValidationError is a ValueError).
_CONVERSION_ERRORS = (ValueError, TypeError, AttributeError)


class SaveFileBusyError(RuntimeError):
    """Raised when the save file kept changing while being read.

    The game was writing it; this is transient and the read can be retried.
    """


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
        SaveFileBusyError: If the game kept writing the file while it was read.
        RuntimeError: If parsing fails.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            raw_stockpiles = fs_sav.parse_save(
                str(path),
                public=public,
                reserves=reserves,
                hex=hex_filter,
                stockpile_type=stockpile_type,
                with_items=with_items,
            )
        except RuntimeError as e:
            if _FILE_BUSY_MARKER in str(e):
                raise SaveFileBusyError(str(e)) from e
            raise
        finally:
            _log_warnings(caught)

    if not isinstance(raw_stockpiles, list):
        raise RuntimeError(f"fs_sav.parse_save returned unexpected type: {type(raw_stockpiles)}")

    return [_convert_or_report(s) for s in raw_stockpiles]


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
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        raw_stockpiles = fs_sav.parse_save_bytes(
            data,
            public=public,
            reserves=reserves,
            hex=hex_filter,
            stockpile_type=stockpile_type,
            with_items=with_items,
        )
    _log_warnings(caught)

    if not isinstance(raw_stockpiles, list):
        raise RuntimeError(
            f"fs_sav.parse_save_bytes returned unexpected type: {type(raw_stockpiles)}"
        )

    return [_convert_or_report(s) for s in raw_stockpiles]


def info() -> dict[str, str]:
    """Get parser info.

    Returns:
        dict[str, str]: Parser implementation and version info.
    """
    result: dict[str, str] = fs_sav.info()
    return result


def _log_warnings(caught: list[warnings.WarningMessage]) -> None:
    """Log the warnings fs-sav emitted while parsing instead of printing them to stderr.

    fs-sav warns about each pinned tooltip it skips (e.g. a structure of the
    other faction, or one the game had no details for).

    Args:
        caught (list[warnings.WarningMessage]): Warnings recorded during the parse.
    """
    for warning in caught:
        logger.warning("fs-sav: %s", warning.message)


def _describe_error(error: Exception) -> str:
    """Describe a conversion error in one line.

    Args:
        error (Exception): The error raised by the conversion.

    Returns:
        str: The reason, without pydantic's multi-line layout.
    """
    if isinstance(error, ValidationError):
        return "; ".join(detail["msg"] for detail in error.errors())
    return str(error)


def _convert_valid_data(data: dict[str, Any]) -> Stockpile:
    """Convert what is valid of a stockpile that failed to convert.

    Args:
        data (dict[str, Any]): Raw stockpile data from fs-sav.

    Returns:
        Stockpile: The stockpile without its type-specific data or, if the rest
            is invalid too, with only what identifies it.
    """
    try:
        return _convert_to_stockpile(
            {key: value for key, value in data.items() if key not in _TYPE_SPECIFIC_FIELDS}
        )
    except _CONVERSION_ERRORS:
        hex_name = data.get("hex")
        return Stockpile(
            name=str(data.get("name", "")),
            type=str(data.get("type", StockpileType.UNDEFINED)),
            hex=hex_name if isinstance(hex_name, str) else None,
        )


def _convert_or_report(data: dict[str, Any]) -> Stockpile:
    """Convert fs-sav output, reporting a failure on the stockpile itself.

    One unexpected stockpile must not lose all the others in the save file, so
    the error is logged and added to the stockpile's ``errors``.

    Args:
        data (dict[str, Any]): Raw stockpile data from fs-sav.

    Returns:
        Stockpile: The converted stockpile or, on failure, its valid data and the error.
    """
    try:
        return _convert_to_stockpile(data)
    except _CONVERSION_ERRORS as e:
        reason = _describe_error(e)

    logger.error(
        "Could not fully read stockpile '%s' (%s) in %s: %s",
        data.get("name"),
        data.get("type"),
        data.get("hex"),
        reason,
    )
    return _convert_valid_data(data).model_copy(
        update={"errors": [f"Could not fully read this stockpile: {reason}"]}
    )


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

    tech_data = data.get("tech")
    tech = StockpileTech.model_validate(tech_data) if tech_data else None

    refinery_data = data.get("refinery")
    refinery = Refinery.model_validate(refinery_data) if refinery_data else None

    factory_orders_data = data.get("factory_orders")
    factory_orders = (
        [FactoryOrder.model_validate(order) for order in factory_orders_data]
        if factory_orders_data
        else None
    )

    return Stockpile(
        name=data.get("name", ""),
        type=stockpile_type,
        faction=ItemFaction.parse_optional(data.get("faction")),
        hex=data.get("hex"),
        coords=coords,
        is_reserve=data.get("is_reserve", False),
        items=items,
        tech=tech,
        refinery=refinery,
        factory_orders=factory_orders,
        timestamp=timestamp,
        raw_timestamp=None,  # fs-sav doesn't expose raw ticks
    )
