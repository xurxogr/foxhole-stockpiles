"""Choosing which stockpiles of a send are merged into one."""

import pytest

from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_group import StockpileGroup
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.catalog_service import CatalogService
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText
from foxhole_stockpiles.services.stockpile_selection.aggregation import AGGREGATE_NAME
from foxhole_stockpiles.services.stockpile_selection.grouping import group_stockpiles

_PORT = StockpileCoords(x=0.1, y=0.2)
_DEPOT = StockpileCoords(x=0.5, y=0.6)


def _stockpile(
    name: str,
    hex_code: str | None = None,
    coords: StockpileCoords | None = None,
    stockpile_type: StockpileType = StockpileType.SEAPORT,
) -> Stockpile:
    return Stockpile(
        name=name,
        type=stockpile_type,
        hex=hex_code,
        coords=coords,
        is_reserve=name != "Public",
        items=[StockpileItem(code="Rifle", quantity=1)],
    )


def _group(
    stockpiles: list[Stockpile],
    grouping: StockpileGrouping,
    group_name: str | None = None,
    language: str = "en",
) -> list[StockpileGroup]:
    return group_stockpiles(
        stockpiles=stockpiles,
        grouping=grouping,
        group_name=group_name,
        labels=ImageText(catalog=CatalogService(), language=language),
    )


def _names(
    grouping: StockpileGrouping, stockpiles: list[Stockpile], group_name: str | None = None
) -> list[str]:
    return [group.drawn.name for group in _group(stockpiles, grouping, group_name)]


def test_nothing_is_grouped_with_none() -> None:
    """Each stockpile stands for itself."""
    stockpiles = [_stockpile("A", "WestgateHex"), _stockpile("B", "WestgateHex")]

    groups = _group(stockpiles, StockpileGrouping.NONE)

    assert [group.drawn for group in groups] == stockpiles
    assert [group.sources for group in groups] == [[stockpiles[0]], [stockpiles[1]]]


def test_all_of_them_become_one() -> None:
    """Whatever their hex."""
    stockpiles = [_stockpile("A", "WestgateHex"), _stockpile("B", "HeartlandsHex")]

    groups = _group(stockpiles, StockpileGrouping.ALL)

    assert [group.drawn.name for group in groups] == [AGGREGATE_NAME]
    assert groups[0].sources == stockpiles
    assert groups[0].drawn.items[0].quantity == 2


def test_the_default_name_is_in_the_language_of_the_output() -> None:
    """The labels say it."""
    stockpiles = [_stockpile("A"), _stockpile("B")]

    groups = _group(stockpiles, StockpileGrouping.ALL, language="es")

    assert groups[0].drawn.name == "Todos los stockpiles"


def test_by_hex_each_hex_is_one_merge_named_after_it() -> None:
    """In the order of their first stockpile."""
    stockpiles = [
        _stockpile("A", "WestgateHex"),
        _stockpile("B", "HeartlandsHex"),
        _stockpile("C", "WestgateHex"),
    ]

    assert _names(StockpileGrouping.HEX, stockpiles) == ["Westgate", "B"]


def test_by_location_the_stockpiles_of_one_place_are_named_by_its_type() -> None:
    """The public and reserve stockpiles of a seaport, but not another place of the hex."""
    stockpiles = [
        _stockpile("Public", "WestgateHex", _PORT),
        _stockpile("Reserve", "WestgateHex", _PORT),
        _stockpile("Depot", "WestgateHex", _DEPOT, StockpileType.STORAGE_DEPOT),
    ]

    assert _names(StockpileGrouping.LOCATION, stockpiles) == ["Seaport", "Depot"]


def test_the_same_coordinates_in_another_hex_are_another_place() -> None:
    """Coordinates are relative to the map of a hex."""
    stockpiles = [_stockpile("A", "WestgateHex", _PORT), _stockpile("B", "HeartlandsHex", _PORT)]

    assert _names(StockpileGrouping.LOCATION, stockpiles) == ["A", "B"]


def test_a_place_with_several_types_is_named_for_all_its_stockpiles() -> None:
    """No single type describes it."""
    stockpiles = [
        _stockpile("A", "WestgateHex", _PORT),
        _stockpile("B", "WestgateHex", _PORT, StockpileType.STORAGE_DEPOT),
    ]

    assert _names(StockpileGrouping.LOCATION, stockpiles) == [AGGREGATE_NAME]


@pytest.mark.parametrize("grouping", [StockpileGrouping.HEX, StockpileGrouping.LOCATION])
def test_stockpiles_without_the_place_are_not_grouped(grouping: StockpileGrouping) -> None:
    """Those of screenshots have no hex or coordinates."""
    stockpiles = [_stockpile("A"), _stockpile("B")]

    assert _names(grouping, stockpiles) == ["A", "B"]


def test_a_lone_stockpile_keeps_its_name_and_type() -> None:
    """Merging one stockpile would only lose its name and type."""
    seaport = _stockpile("Public", "WestgateHex")

    groups = _group([seaport], StockpileGrouping.ALL, "Report")

    assert [group.drawn for group in groups] == [seaport]


def test_the_group_name_names_each_merge_with_its_values() -> None:
    """Its {name} is the name the merge would have had."""
    stockpiles = [
        _stockpile("A", "WestgateHex"),
        _stockpile("B", "WestgateHex"),
        _stockpile("C", "HeartlandsHex"),
        _stockpile("D", "HeartlandsHex"),
    ]

    assert _names(StockpileGrouping.HEX, stockpiles, "Stock: {name}") == [
        "Stock: Westgate",
        "Stock: Heartlands",
    ]


def test_a_blank_group_name_leaves_the_default_name() -> None:
    """Spaces are not a name."""
    stockpiles = [_stockpile("A"), _stockpile("B")]

    assert _names(StockpileGrouping.ALL, stockpiles, "  ") == [AGGREGATE_NAME]


def test_no_stockpiles_make_no_groups() -> None:
    """There is nothing to send."""
    assert _group([], StockpileGrouping.ALL) == []
