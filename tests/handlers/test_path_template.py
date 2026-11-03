"""The templates of the output file paths."""

from foxhole_stockpiles.handlers.path_template import fill_path_template, with_extension
from foxhole_stockpiles.models.stockpile import Stockpile


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
