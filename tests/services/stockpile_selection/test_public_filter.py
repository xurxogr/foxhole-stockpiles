"""Leaving out the public stockpiles an output does not want."""

import pytest

from foxhole_stockpiles.enums.public_stockpile_filter import PublicStockpileFilter
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_selection.public_filter import filter_public

_SEAPORT_PUBLIC = Stockpile(name="Public", type=StockpileType.SEAPORT)
_SEAPORT_RESERVE = Stockpile(name="Reserve", type=StockpileType.SEAPORT, is_reserve=True)
_DEPOT_PUBLIC = Stockpile(name="Public", type=StockpileType.STORAGE_DEPOT)
_AIRCRAFT_PUBLIC = Stockpile(name="Public", type=StockpileType.AIRCRAFT_DEPOT)
_BUNKER_PUBLIC = Stockpile(name="Public", type=StockpileType.BUNKER_BASE_1)
_ALL = [_SEAPORT_PUBLIC, _SEAPORT_RESERVE, _DEPOT_PUBLIC, _AIRCRAFT_PUBLIC, _BUNKER_PUBLIC]


@pytest.mark.parametrize(
    ("public_stockpiles", "expected"),
    [
        (PublicStockpileFilter.ALL, _ALL),
        (PublicStockpileFilter.NONE, [_SEAPORT_RESERVE]),
        (PublicStockpileFilter.NON_RESERVABLE, [_SEAPORT_RESERVE, _BUNKER_PUBLIC]),
    ],
)
def test_reserves_always_pass_and_public_stockpiles_as_asked(
    public_stockpiles: PublicStockpileFilter, expected: list[Stockpile]
) -> None:
    """In a seaport, a storage depot or an aircraft depot the reserves are what matters."""
    assert filter_public(stockpiles=_ALL, public_stockpiles=public_stockpiles) == expected


def test_a_public_stockpile_of_an_unknown_type_is_kept_outside_reservable_structures() -> None:
    """Nothing says it could hold reserves, as in a screenshot without a type."""
    unknown = Stockpile(name="Public")

    assert filter_public(
        stockpiles=[unknown], public_stockpiles=PublicStockpileFilter.NON_RESERVABLE
    ) == [unknown]


@pytest.mark.parametrize(
    ("stockpile_type", "has_reserves"),
    [
        (StockpileType.SEAPORT, True),
        (StockpileType.STORAGE_DEPOT, True),
        (StockpileType.AIRCRAFT_DEPOT, True),
        (StockpileType.BUNKER_BASE_1, False),
        (StockpileType.SAFE_HOUSE, False),
        ("NewStructure", False),
    ],
)
def test_the_structures_that_hold_reserves(stockpile_type: str, has_reserves: bool) -> None:
    """Those the game gives reserve stockpiles."""
    assert StockpileType.has_reserves(stockpile_type) is has_reserves
