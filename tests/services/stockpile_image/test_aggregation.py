"""Merging several stockpiles into one image."""

from datetime import UTC, datetime

from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.stockpile_image.aggregation import (
    AGGREGATE_NAME,
    aggregate,
    merge_items,
    stockpiles_to_draw,
)


def _item(code: str, quantity: int, crated: bool = False) -> StockpileItem:
    return StockpileItem(code=code, quantity=quantity, crated=crated)


def test_quantities_of_the_same_item_are_added() -> None:
    """Each item appears once."""
    merged = merge_items([_item("Rifle", 5), _item("Rifle", 7), _item("Bayonet", 1)])

    assert [(item.code, item.quantity) for item in merged] == [("Bayonet", 1), ("Rifle", 12)]


def test_crated_and_loose_items_stay_apart() -> None:
    """They are different goods, so a sum of both would mean nothing."""
    merged = merge_items([_item("Rifle", 5), _item("Rifle", 2, crated=True)])

    assert [(item.quantity, item.crated) for item in merged] == [(5, False), (2, True)]


def test_an_unknown_quantity_makes_the_total_unknown() -> None:
    """Whatever its position: a number would hide the stock that could not be read."""
    for quantities in ([5, -1, 7], [-1, 5], [5, -1]):
        merged = merge_items([_item("Rifle", quantity) for quantity in quantities])

        assert [item.quantity for item in merged] == [-1]


def test_merging_does_not_change_the_stockpiles() -> None:
    """The other handlers receive them as they were."""
    first = Stockpile(name="A", items=[_item("Rifle", 5)])
    second = Stockpile(name="B", items=[_item("Rifle", 7)])

    aggregate([first, second])

    assert first.items[0].quantity == 5
    assert second.items[0].quantity == 7


def test_the_result_is_named_for_all_the_stockpiles() -> None:
    """A single name or type no longer applies."""
    merged = aggregate([Stockpile(name="A", type=StockpileType.SEAPORT), Stockpile(name="B")])

    assert merged.name == AGGREGATE_NAME
    assert merged.type == StockpileType.UNDEFINED


def test_the_newest_timestamp_is_kept() -> None:
    """Even mixing the naive times of a scan with the aware ones of a save file."""
    newest = datetime(2030, 1, 1, tzinfo=UTC)
    stockpiles = [
        Stockpile(name="A", timestamp=datetime(2020, 1, 1)),
        Stockpile(name="B", timestamp=newest),
    ]

    assert aggregate(stockpiles).timestamp == newest


def test_what_all_of_them_share_is_kept() -> None:
    """The hex of a report about one hex still applies."""
    same = aggregate([Stockpile(name="A", hex="Westgate"), Stockpile(name="B", hex="Westgate")])
    mixed = aggregate([Stockpile(name="A", hex="Westgate"), Stockpile(name="B", hex="Callahan")])

    assert same.hex == "Westgate"
    assert mixed.hex is None


def test_nothing_is_merged_unless_asked() -> None:
    """Each stockpile has its own image by default."""
    stockpiles = [Stockpile(name="A"), Stockpile(name="B")]

    assert stockpiles_to_draw(settings=StockpileImageSettings(), stockpiles=stockpiles) == (
        stockpiles
    )


def test_merging_when_asked() -> None:
    """All of them become one."""
    stockpiles = [Stockpile(name="A"), Stockpile(name="B")]

    drawn = stockpiles_to_draw(
        settings=StockpileImageSettings(aggregate=True), stockpiles=stockpiles
    )

    assert [stockpile.name for stockpile in drawn] == [AGGREGATE_NAME]


def test_no_stockpiles_are_not_merged_into_an_empty_image() -> None:
    """There is nothing to draw."""
    assert stockpiles_to_draw(settings=StockpileImageSettings(aggregate=True), stockpiles=[]) == []
