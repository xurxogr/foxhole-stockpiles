"""Choose which stockpiles of a send are merged into one.

A save file holds many stockpiles, and one message or row each can flood a channel.
"""

from collections.abc import Hashable

from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_group import StockpileGroup
from foxhole_stockpiles.services.stockpile_image.placeholders import coords_text, hex_name
from foxhole_stockpiles.services.stockpile_selection.aggregation import aggregate
from foxhole_stockpiles.services.stockpile_selection.group_labels import GroupLabels


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


def _place_name(stockpile: Stockpile) -> str:
    """Name the place of a stockpile by its hex and its town, or its coordinates.

    Args:
        stockpile (Stockpile): A stockpile with coordinates.

    Returns:
        str: Such as ``Westgate - Lord's Mouth``, or ``Westgate - X: 0.46 Y: 0.66``
            when its town is not known.
    """
    parts = (hex_name(stockpile.hex), stockpile.town or coords_text(stockpile))
    return " - ".join(part for part in parts if part)


def _merge_name(grouping: StockpileGrouping, sources: list[Stockpile], labels: GroupLabels) -> str:
    """Name a merge by what its stockpiles share.

    Args:
        grouping (StockpileGrouping): How the stockpiles were grouped.
        sources (list[Stockpile]): The stockpiles of the group.
        labels (GroupLabels): The text in the language of the output.

    Returns:
        str: The hex of a hex, the hex and position of a place, or "All Stockpiles".
    """
    first = sources[0]
    if grouping == StockpileGrouping.HEX and first.hex:
        return hex_name(first.hex)
    if grouping == StockpileGrouping.LOCATION and first.coords:
        return _place_name(first)
    return labels.all_stockpiles()


def group_stockpiles(
    stockpiles: list[Stockpile],
    grouping: StockpileGrouping,
    labels: GroupLabels,
) -> list[StockpileGroup]:
    """Choose what an output receives for each group of a send.

    Args:
        stockpiles (list[Stockpile]): The stockpiles of the send.
        grouping (StockpileGrouping): How to group them.
        labels (GroupLabels): The text in the language of the output.

    Returns:
        list[StockpileGroup]: One per group, in the order of their first stockpile.
            A lone stockpile keeps its own name and type.
    """
    groups: dict[Hashable, list[Stockpile]] = {}
    for index, stockpile in enumerate(stockpiles):
        key = _group_key(grouping=grouping, stockpile=stockpile, index=index)
        groups.setdefault(key, []).append(stockpile)

    return [
        StockpileGroup(
            drawn=sources[0]
            if len(sources) == 1
            else aggregate(
                stockpiles=sources,
                name=_merge_name(grouping=grouping, sources=sources, labels=labels),
            ),
            sources=sources,
        )
        for sources in groups.values()
    ]
