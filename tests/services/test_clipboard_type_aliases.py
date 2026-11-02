"""Tests for the stockpile type names the clipboard parser recognizes."""

import pytest

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.services.clipboard_parser.type_aliases import _type_from_display


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("Flugzeugdepot", StockpileType.AIRCRAFT_DEPOT),
        ("Entrepôt à Avions", StockpileType.AIRCRAFT_DEPOT),
        ("Depósito de Aeronaves", StockpileType.AIRCRAFT_DEPOT),
        ("Авиационный склад", StockpileType.AIRCRAFT_DEPOT),
        ("飞行器储备站", StockpileType.AIRCRAFT_DEPOT),
        ("储备站", StockpileType.STORAGE_DEPOT),
        ("Torre", StockpileType.KEEP),
        ("Stadthalle", StockpileType.TOWN_BASE_1),
    ],
)
def test_recognizes_the_names_the_game_uses(display: str, expected: StockpileType) -> None:
    """Every language's name from the game maps to its stockpile type."""
    assert _type_from_display(display) == expected


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("仓库", StockpileType.STORAGE_DEPOT),
        ("Torreão", StockpileType.KEEP),
        ("Town Hall", StockpileType.TOWN_BASE_1),
        ("Stadtkernbasis", StockpileType.TOWN_BASE_1),
    ],
)
def test_keeps_recognizing_names_the_game_no_longer_uses(
    display: str, expected: StockpileType
) -> None:
    """Names kept in the table for exports from other game versions still map."""
    assert _type_from_display(display) == expected
