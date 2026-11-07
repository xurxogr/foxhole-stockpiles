"""Choose which stockpiles of a send share an image.

A save file holds many stockpiles, and one image each can flood a channel.
"""

from collections.abc import Hashable

from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_group import StockpileGroup
from foxhole_stockpiles.services.catalog_service import get_catalog_service
from foxhole_stockpiles.services.stockpile_image.aggregation import aggregate
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText
from foxhole_stockpiles.services.stockpile_image.placeholders import hex_name
from foxhole_stockpiles.services.stockpile_image.rendering import fill_stockpile_text


def _group_key(grouping: StockpileGrouping, stockpile: Stockpile, index: int) -> Hashable:
    """Tell which group a stockpile belongs to.

    A stockpile without the hex or the place the grouping needs, such as one from a
    screenshot, is left alone: it cannot be told apart from another one.

    Args:
        grouping (StockpileGrouping): How the stockpiles are grouped.
        stockpile (Stockpile): The stockpile.
        index (int): Its position in the send.

    Returns:
        Hashable: The same value for the stockpiles of one group.
    """
    alone = ("alone", index)
    if grouping == StockpileGrouping.ALL:
        return "all"
    if grouping == StockpileGrouping.HEX:
        return ("hex", stockpile.hex) if stockpile.hex else alone
    if grouping == StockpileGrouping.LOCATION and stockpile.coords:
        return ("location", stockpile.hex, stockpile.coords.to_key())
    return alone


def _default_name(grouping: StockpileGrouping, sources: list[Stockpile], labels: ImageText) -> str:
    """Name a merge by what its stockpiles share.

    Args:
        grouping (StockpileGrouping): How the stockpiles were grouped.
        sources (list[Stockpile]): The stockpiles of the group.
        labels (ImageText): The text in the language of the output.

    Returns:
        str: The hex of a hex, the type of a place, or "All Stockpiles".
    """
    if grouping == StockpileGrouping.HEX and sources[0].hex:
        return hex_name(sources[0].hex)
    types = {stockpile.type for stockpile in sources}
    if grouping == StockpileGrouping.LOCATION and len(types) == 1:
        shared_type = labels.stockpile_type(types.pop())
        if shared_type:
            return shared_type
    return labels.all_stockpiles()


def _merge(
    settings: StockpileImageSettings, sources: list[Stockpile], labels: ImageText
) -> Stockpile:
    """Merge the stockpiles of a group, named with the headline.

    Args:
        settings (StockpileImageSettings): How to draw them.
        sources (list[Stockpile]): The stockpiles of the group, more than one.
        labels (ImageText): The text in the language of the output.

    Returns:
        Stockpile: Their merge.
    """
    merged = aggregate(
        stockpiles=sources,
        name=_default_name(grouping=settings.grouping, sources=sources, labels=labels),
    )
    headline = fill_stockpile_text(settings=settings, template=settings.headline, stockpile=merged)
    return merged.model_copy(update={"name": headline}) if headline else merged


def group_stockpiles(
    settings: StockpileImageSettings, stockpiles: list[Stockpile]
) -> list[StockpileGroup]:
    """Choose what each image of a send shows.

    Args:
        settings (StockpileImageSettings): How to draw them.
        stockpiles (list[Stockpile]): The stockpiles of the send.

    Returns:
        list[StockpileGroup]: One per image, in the order of their first stockpile. A
            lone stockpile keeps its own name and type.
    """
    groups: dict[Hashable, list[Stockpile]] = {}
    for index, stockpile in enumerate(stockpiles):
        key = _group_key(grouping=settings.grouping, stockpile=stockpile, index=index)
        groups.setdefault(key, []).append(stockpile)

    labels = ImageText(catalog=get_catalog_service(), language=settings.language)
    return [
        StockpileGroup(
            drawn=sources[0]
            if len(sources) == 1
            else _merge(settings=settings, sources=sources, labels=labels),
            sources=sources,
        )
        for sources in groups.values()
    ]
