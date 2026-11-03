"""Drawing a stockpile as images."""

import io
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from PIL import Image

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.stockpile_image import layout, renderer
from foxhole_stockpiles.services.stockpile_image.font_selector import FontSelector
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText
from foxhole_stockpiles.services.stockpile_image.renderer import StockpileImageRenderer

_MARK = (1, 200, 3)


class _Catalog:
    """A catalog that names items after their code."""

    def get_display_name(self, code: str, language: str | None = None) -> str:
        """Get the name of an item.

        Args:
            code (str): Its code.
            language (str | None): Not used.

        Returns:
            str: The code.
        """
        return code

    def get_category(self, code: str) -> str | None:
        """Get the category of an item.

        Args:
            code (str): Its code.

        Returns:
            str | None: The same one for all.
        """
        return "Small Arms"


def _stockpile(count: int = 3) -> Stockpile:
    return Stockpile(
        name="Depot",
        hex="Westgate",
        timestamp=datetime(2026, 1, 4, 9, 0, tzinfo=UTC),
        items=[StockpileItem(code=f"Item{index}", quantity=index) for index in range(count)],
    )


def _render(stockpile: Stockpile, icons: dict[Any, Image.Image] | None = None) -> list[Image.Image]:
    drawer = StockpileImageRenderer(
        text=ImageText(catalog=_Catalog(), language="en"),
        font_selector=FontSelector(),
        icons=icons or {},
    )
    return [
        Image.open(io.BytesIO(png)) for png in drawer.render_png(stockpile=stockpile, headline=None)
    ]


def _has_color(image: Image.Image, color: tuple[int, int, int]) -> bool:
    return any(found == color for _, found in image.convert("RGB").getcolors(maxcolors=1 << 24))


def test_each_page_is_a_png() -> None:
    """A normal stockpile fits in one image."""
    images = _render(_stockpile())

    assert len(images) == 1
    assert images[0].format == "PNG"


def test_a_stockpile_too_long_for_a_page_gives_several_images(monkeypatch: Any) -> None:
    """Each one stays readable."""
    monkeypatch.setattr(layout, "MAX_COLUMN_LINES", 4)
    monkeypatch.setattr(layout, "MAX_PAGE_COLUMNS", 1)

    assert len(_render(_stockpile(count=10))) > 1


def test_more_lines_make_a_taller_image() -> None:
    """The rows never overlap the header or the footer."""
    short, tall = _render(_stockpile(count=1))[0], _render(_stockpile(count=5))[0]

    assert tall.height - short.height == 4 * renderer.ROW_HEIGHT


def test_more_columns_make_a_wider_image(monkeypatch: Any) -> None:
    """Each column has its own width."""
    monkeypatch.setattr(layout, "MAX_COLUMN_LINES", 4)

    narrow, wide = _render(_stockpile(count=2))[0], _render(_stockpile(count=9))[0]

    assert wide.width > narrow.width


def test_the_icon_of_an_item_is_drawn() -> None:
    """A row shows the icon the database has for that code and crate state."""
    icon = Image.new("RGB", (32, 32), _MARK)

    drawn = _render(_stockpile(count=1), icons={("Item0", False): icon})[0]

    assert _has_color(drawn, _MARK)


def test_a_crate_does_not_use_the_icon_of_a_loose_item_if_it_has_its_own() -> None:
    """The icons differ."""
    stockpile = Stockpile(items=[StockpileItem(code="Item0", quantity=1, crated=True)])
    icons = {
        ("Item0", False): Image.new("RGB", (32, 32), _MARK),
        ("Item0", True): Image.new("RGB", (32, 32), (9, 9, 250)),
    }

    drawn = _render(stockpile, icons=icons)[0]

    assert _has_color(drawn, (9, 9, 250))
    assert not _has_color(drawn, _MARK)


def test_a_crate_without_its_own_icon_uses_the_loose_one() -> None:
    """Its heading already says that they are crates."""
    stockpile = Stockpile(items=[StockpileItem(code="Item0", quantity=1, crated=True)])

    drawn = _render(stockpile, icons={("Item0", False): Image.new("RGB", (32, 32), _MARK)})[0]

    assert _has_color(drawn, _MARK)


def test_a_row_without_an_icon_is_still_drawn() -> None:
    """Without a database the image has text only."""
    assert _render(_stockpile())[0].width > 0


def test_a_stockpile_without_items_gives_an_image() -> None:
    """It says so instead of failing."""
    assert len(_render(Stockpile(name="Empty"))) == 1


def test_a_very_long_name_does_not_widen_the_image() -> None:
    """A name from the game cannot break the layout."""
    stockpile = Stockpile(items=[StockpileItem(code="x" * 300, quantity=1)])

    assert _render(stockpile)[0].width == _render(_stockpile(count=1))[0].width


def test_the_headline_can_be_given() -> None:
    """A long one is shortened to fit, and does not change the size."""
    drawer = StockpileImageRenderer(
        text=ImageText(catalog=_Catalog(), language="en"), font_selector=FontSelector(), icons={}
    )

    assert drawer.render_png(stockpile=_stockpile(), headline="H" * 500)


def test_shorten_cuts_a_text_that_does_not_fit() -> None:
    """A shortened text says that it was shortened."""
    font = FontSelector().font_for(text="abc", size=16)

    shortened = renderer.shorten(text="a" * 200, font=font, max_width=100)

    assert shortened.endswith("...")
    assert font.getlength(shortened) <= 100
    assert renderer.shorten(text="abc", font=font, max_width=1000) == "abc"


def _drawn_texts(stockpile: Stockpile, language: str = "en") -> list[str]:
    drawer = StockpileImageRenderer(
        text=ImageText(catalog=_Catalog(), language=language),
        font_selector=FontSelector(),
        icons={},
    )
    with patch.object(drawer, "_text", wraps=drawer._text) as spy:
        drawer.render_png(stockpile=stockpile, headline=None)
    return [call.kwargs["text"] for call in spy.call_args_list]


def test_an_unknown_type_is_not_drawn_under_the_title() -> None:
    """Only what locates the stockpile, if there is anything."""
    texts = _drawn_texts(Stockpile(name="Depot", hex="Westgate"))

    assert "Westgate" in texts
    assert not any("Undefined" in text for text in texts)


def test_a_known_type_is_drawn_by_its_name_in_the_language_of_the_image() -> None:
    """Not by the code of the game."""
    stockpile = Stockpile(name="Depot", type=StockpileType.ENCAMPMENT, hex="Westgate")

    assert "Feldlager · Westgate" in _drawn_texts(stockpile, language="de")


def test_a_stockpile_without_name_or_known_type_has_no_title() -> None:
    """Rather than an internal value."""
    assert _drawn_texts(Stockpile())[0] == ""


def test_the_fixed_text_is_in_the_language_of_the_image() -> None:
    """The total and the empty stockpile."""
    texts = _drawn_texts(Stockpile(name="Depot"), language="de")

    assert "Keine Gegenstände" in texts
    assert any(text.startswith("Gesamt: 0") for text in texts)
