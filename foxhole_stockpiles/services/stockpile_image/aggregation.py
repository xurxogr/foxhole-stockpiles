"""Merge several stockpiles into one image.

A save file holds many stockpiles, and one image each can flood a channel.

Based on the aggregator of the feat/discord-image-output branch by Gabylot.
"""

from collections.abc import Callable
from typing import Final

from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.catalog_service import get_catalog_service
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText

AGGREGATE_NAME: Final[str] = "All Stockpiles"
_UNKNOWN: Final[int] = -1


def merge_items(items: list[StockpileItem]) -> list[StockpileItem]:
    """Add up the items of several stockpiles.

    Crated and loose items stay apart. An unknown quantity makes the total of its
    item unknown, as a number would hide the stock that could not be read.

    Args:
        items (list[StockpileItem]): The items.

    Returns:
        list[StockpileItem]: One item per code and crated state, sorted by them.
    """
    totals: dict[tuple[str, bool], int] = {}
    for item in items:
        key = (item.code, item.crated)
        total = totals.get(key, 0)
        unknown = item.quantity == _UNKNOWN or total == _UNKNOWN
        totals[key] = _UNKNOWN if unknown else total + item.quantity
    return [
        StockpileItem(code=code, quantity=total, crated=crated)
        for (code, crated), total in sorted(totals.items())
    ]


def _shared[T](stockpiles: list[Stockpile], read: Callable[[Stockpile], T | None]) -> T | None:
    """Read a value all the stockpiles have in common.

    Args:
        stockpiles (list[Stockpile]): The stockpiles.
        read (Callable[[Stockpile], T | None]): What reads the value of one.

    Returns:
        T | None: The value, or None if they differ.
    """
    values = {read(stockpile) for stockpile in stockpiles}
    return values.pop() if len(values) == 1 else None


def aggregate(stockpiles: list[Stockpile], name: str = AGGREGATE_NAME) -> Stockpile:
    """Merge some stockpiles into a new one.

    Args:
        stockpiles (list[Stockpile]): The stockpiles, at least one.
        name (str): The name of the result.

    Returns:
        Stockpile: Their items, with the newest timestamp and what they share.
    """
    # Scans have naive times and save files aware ones, which cannot be compared.
    newest = max(stockpiles, key=lambda stockpile: stockpile.timestamp.timestamp())
    return Stockpile(
        name=name,
        type=StockpileType.UNDEFINED,
        hex=_shared(stockpiles=stockpiles, read=lambda stockpile: stockpile.hex),
        shard=_shared(stockpiles=stockpiles, read=lambda stockpile: stockpile.shard),
        faction=_shared(stockpiles=stockpiles, read=lambda stockpile: stockpile.faction),
        timestamp=newest.timestamp,
        ingame_timestamp=newest.ingame_timestamp,
        items=merge_items([item for stockpile in stockpiles for item in stockpile.items]),
    )


def stockpiles_to_draw(
    settings: StockpileImageSettings, stockpiles: list[Stockpile]
) -> list[Stockpile]:
    """Choose what gets an image of its own.

    Args:
        settings (StockpileImageSettings): How to draw them.
        stockpiles (list[Stockpile]): The stockpiles of a batch.

    Returns:
        list[Stockpile]: The same stockpiles, or their merge if the settings ask for it.
    """
    if settings.aggregate and stockpiles:
        labels = ImageText(catalog=get_catalog_service(), language=settings.language)
        return [aggregate(stockpiles=stockpiles, name=labels.all_stockpiles())]
    return stockpiles
