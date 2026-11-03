"""The templates of the text around a stockpile image."""

from datetime import UTC, datetime

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.stockpile_image.placeholders import fill_template


def _stockpile() -> Stockpile:
    return Stockpile(
        name="Depot",
        hex="Westgate",
        timestamp=datetime(2026, 1, 4, 9, 0, tzinfo=UTC),
        items=[
            StockpileItem(code="a", quantity=5),
            StockpileItem(code="b", quantity=-1),
        ],
    )


def test_values_of_the_stockpile_are_filled_in() -> None:
    """An unknown quantity does not reduce the total."""
    filled = fill_template(
        template="{name} {hex} {timestamp} {item_count} {total_items}", stockpile=_stockpile()
    )

    assert filled == "Depot Westgate 2026-01-04 09:00 2 5"


def test_missing_value_is_left_empty() -> None:
    """A stockpile from a screenshot has no hex."""
    assert fill_template(template="[{hex}]", stockpile=Stockpile()) == "[]"


def test_unknown_placeholder_and_stray_braces_stay_as_written() -> None:
    """A typo shows up as text instead of failing the send."""
    assert fill_template(template="{nope} {", stockpile=_stockpile()) == "{nope} {"


def test_a_template_cannot_reach_into_the_values() -> None:
    """Only the listed placeholders are replaced, unlike with str.format."""
    template = "{name.__class__}"

    assert fill_template(template=template, stockpile=_stockpile()) == template


def test_a_value_is_not_expanded_again() -> None:
    """A stockpile named like a placeholder does not reveal another value."""
    stockpile = Stockpile(name="{hex}", hex="Westgate")

    assert fill_template(template="{name}", stockpile=stockpile) == "{hex}"
