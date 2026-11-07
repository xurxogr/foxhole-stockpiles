"""Choose which stockpiles of a send are merged into one.

A save file holds many stockpiles, and one message or row each can flood a channel.
"""

from collections.abc import Hashable

from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_group import StockpileGroup
from foxhole_stockpiles.services.stockpile_image.placeholders import fill_template, hex_name
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


def _default_name(
    grouping: StockpileGrouping, sources: list[Stockpile], labels: GroupLabels
) -> str:
    """Name a merge by what its stockpiles share.

    Args:
        grouping (StockpileGrouping): How the stockpiles were grouped.
        sources (list[Stockpile]): The stockpiles of the group.
        labels (GroupLabels): The text in the language of the output.

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
    grouping: StockpileGrouping,
    group_name: str | None,
    sources: list[Stockpile],
    labels: GroupLabels,
) -> Stockpile:
    """Merge the stockpiles of a group and name it.

    Args:
        grouping (StockpileGrouping): How the stockpiles were grouped.
        group_name (str | None): The name template, or None for the default name.
        sources (list[Stockpile]): The stockpiles of the group, more than one.
        labels (GroupLabels): The text in the language of the output.

    Returns:
        Stockpile: Their merge.
    """
    merged = aggregate(
        stockpiles=sources,
        name=_default_name(grouping=grouping, sources=sources, labels=labels),
    )
    template = (group_name or "").strip()
    if not template:
        return merged
    name = fill_template(
        template=template, stockpile=merged, type_label=labels.stockpile_type(merged.type)
    )
    return merged.model_copy(update={"name": name})


def group_stockpiles(
    stockpiles: list[Stockpile],
    grouping: StockpileGrouping,
    group_name: str | None,
    labels: GroupLabels,
) -> list[StockpileGroup]:
    """Choose what an output receives for each group of a send.

    Args:
        stockpiles (list[Stockpile]): The stockpiles of the send.
        grouping (StockpileGrouping): How to group them.
        group_name (str | None): The name of each merge, with placeholders; its
            ``{name}`` is the default name. None or blank for the default name.
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
            else _merge(grouping=grouping, group_name=group_name, sources=sources, labels=labels),
            sources=sources,
        )
        for sources in groups.values()
    ]
