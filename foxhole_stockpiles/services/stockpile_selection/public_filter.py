"""Leave out the public stockpiles an output does not want."""

from foxhole_stockpiles.enums.public_stockpile_filter import PublicStockpileFilter
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile


def _is_wanted(stockpile: Stockpile, public_stockpiles: PublicStockpileFilter) -> bool:
    """Tell whether an output receives a stockpile.

    Args:
        stockpile (Stockpile): The stockpile.
        public_stockpiles (PublicStockpileFilter): Which public stockpiles it receives.

    Returns:
        bool: True for a reserve stockpile, and for a public one the filter lets in.
    """
    if stockpile.is_reserve or public_stockpiles == PublicStockpileFilter.ALL:
        return True
    if public_stockpiles == PublicStockpileFilter.NONE:
        return False
    return not StockpileType.has_reserves(stockpile.type)


def filter_public(
    stockpiles: list[Stockpile], public_stockpiles: PublicStockpileFilter
) -> list[Stockpile]:
    """Leave out the public stockpiles an output does not receive.

    Args:
        stockpiles (list[Stockpile]): The stockpiles of a send.
        public_stockpiles (PublicStockpileFilter): Which public stockpiles it receives.

    Returns:
        list[Stockpile]: The stockpiles it receives, in the same order.
    """
    return [
        stockpile
        for stockpile in stockpiles
        if _is_wanted(stockpile=stockpile, public_stockpiles=public_stockpiles)
    ]
