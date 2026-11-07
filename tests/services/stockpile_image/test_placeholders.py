"""The templates of the text around a stockpile image."""

from datetime import UTC, datetime

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.stockpile_image.placeholders import fill_template, hex_name


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


def test_the_hex_is_written_by_its_name() -> None:
    """Not by the code the game uses."""
    stockpile = Stockpile(hex="HeartlandsHex")

    assert fill_template(template="{hex}", stockpile=stockpile) == "Heartlands"


def test_an_unknown_hex_keeps_its_code() -> None:
    """A new hex is not lost while the application does not know it."""
    assert hex_name("NewHex") == "NewHex"


def test_the_text_accepts_the_names_of_the_paths_too() -> None:
    """One template works in every field: {stockpile_name} as in a path."""
    filled = fill_template(
        template="{stockpile_name} {stockpile_type}", stockpile=_stockpile(), type_label="Seaport"
    )

    assert filled == "Depot Seaport"


def test_the_parts_of_the_date_and_the_position_are_filled_in() -> None:
    """As in a path, from the time of the stockpile."""
    stockpile = _stockpile().model_copy(update={"coords": StockpileCoords(x=0.457, y=0.664)})

    filled = fill_template(
        template="{year}{month}{day} {hour}{minute} {coords}", stockpile=stockpile
    )

    assert filled == "20260104 0900 X: 0.46 Y: 0.66"
