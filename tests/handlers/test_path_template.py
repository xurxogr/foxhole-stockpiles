"""The templates of the output file paths."""

from foxhole_stockpiles.handlers.path_template import fill_path_template, with_extension
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem


def test_placeholders_are_replaced_with_safe_values() -> None:
    """A name others control cannot leave the directory of the template."""
    filled = fill_path_template(
        template="out/{stockpile_name}.png", stockpiles=[Stockpile(name="../../evil")]
    )

    assert filled == "out/_.._evil.png"


def test_several_stockpiles_share_a_generic_name() -> None:
    """One file for several stockpiles cannot be named after the first."""
    filled = fill_path_template(
        template="{stockpile_name}", stockpiles=[Stockpile(name="a"), Stockpile(name="b")]
    )

    assert filled == "multiple_stockpiles"


def test_extension_is_added_or_replaced() -> None:
    """The extension of the path always matches what is written."""
    assert with_extension(path="out/file", extension=".png") == "out/file.png"
    assert with_extension(path="out/file.json", extension=".png") == "out/file.png"


def test_a_path_accepts_the_names_of_the_text_too() -> None:
    """One template works in every field: {name} and {type} as in a message."""
    stockpile = Stockpile(name="Depot", type="Seaport", hex="WestgateHex")

    filled = fill_path_template(template="{hex}_{type}_{name}", stockpiles=[stockpile])

    assert filled == "Westgate_Seaport_Depot"


def test_the_counts_of_a_path_add_up_every_stockpile_written() -> None:
    """A file with several stockpiles counts all of them."""
    stockpiles = [
        Stockpile(items=[StockpileItem(code="a", quantity=2), StockpileItem(code="b", quantity=3)]),
        Stockpile(items=[StockpileItem(code="a", quantity=-1)]),
    ]

    filled = fill_path_template(template="{item_count}-{total_items}", stockpiles=stockpiles)

    assert filled == "3-5"
