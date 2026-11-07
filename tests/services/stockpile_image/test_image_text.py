"""The text of an image, in the language of its output."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections.output import ImageHandlerSettings
from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.i18n import set_language, t
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services import catalog_service
from foxhole_stockpiles.services.catalog_service import CatalogService
from foxhole_stockpiles.services.stockpile_image import rendering
from foxhole_stockpiles.services.stockpile_image.grouping import group_stockpiles
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText
from foxhole_stockpiles.services.stockpile_image.layout import build_pages
from foxhole_stockpiles.services.stockpile_image.rendering import fill_stockpile_text

_TRANSLATIONS = Path(catalog_service.__file__).parent.parent / "i18n" / "translations"
_LANGUAGES = sorted(path.stem for path in _TRANSLATIONS.glob("*.json"))


def _text(language: str = "es", catalog: Any = None) -> ImageText:
    return ImageText(catalog=catalog or CatalogService(), language=language)


def _texts(language: str) -> dict[str, Any]:
    data = json.loads((_TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
    result: dict[str, Any] = data["stockpile_image"]
    return result


def _type_names(language: str) -> dict[str, str]:
    data = json.loads((_TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
    result: dict[str, str] = data["stockpile_types"]
    return result


@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_type_of_stockpile_has_a_name(language: str) -> None:
    """A new type in the enum cannot be forgotten: import the names of the game again."""
    expected = {member.value for member in StockpileType} - {StockpileType.UNDEFINED.value}

    assert expected <= set(_type_names(language))
    assert set(_type_names(language)) == set(_type_names("en"))


@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_language_has_the_same_texts(language: str) -> None:
    """Otherwise a key would be drawn on the image."""
    assert set(_texts(language)) == set(_texts("en"))
    assert set(_texts(language)["categories"]) == set(_texts("en")["categories"])


def test_an_unknown_type_is_not_shown() -> None:
    """It is an internal value, which says nothing to whoever reads the image."""
    assert _text().stockpile_type(StockpileType.UNDEFINED) == ""
    assert _text().stockpile_type("") == ""


def test_a_type_is_shown_by_its_name() -> None:
    """Not by the code the game uses."""
    assert _text("en").stockpile_type(StockpileType.ENCAMPMENT) == "Encampment"
    assert _text("de").stockpile_type(StockpileType.ENCAMPMENT) == "Feldlager"


def test_a_type_without_a_name_is_shown_as_it_came() -> None:
    """A newer game can have types this version does not know."""
    assert _text().stockpile_type("Brand.New Type") == "Brand.New Type"


def test_headings_are_translated() -> None:
    """Crates included."""
    assert _text().category_heading(category="Small Arms", crated=False) == "Armas ligeras"
    assert _text().category_heading(category="Small Arms", crated=True) == "Armas ligeras (cajas)"


def test_a_category_without_a_translation_is_shown_as_it_came() -> None:
    """A newer catalog can have others."""
    assert _text().category_heading(category="New Thing", crated=False) == "New Thing"


def test_the_language_is_not_the_one_of_the_window() -> None:
    """The window can be in one language and the image in another."""
    set_language("de")
    try:
        assert t("stockpile_image.no_items") != _text("es").no_items()
        assert _text("es").no_items() == _texts("es")["no_items"]
    finally:
        set_language("en")


@pytest.mark.parametrize("language", ["xx", "../../secret", ""])
def test_a_language_that_does_not_exist_is_english(language: str, caplog: Any) -> None:
    """The configuration can be edited by hand, and no other file gets read."""
    assert _text(language).no_items() == _texts("en")["no_items"]
    assert "using English" in caplog.text


def test_groups_stay_in_supply_order_in_any_language(tmp_path: Path) -> None:
    """The order comes from the category, not from its translation."""
    path = tmp_path / "catalog.json"
    entries = [
        {"CodeName": "A", "DisplayName": "Aid", "ItemCategory": "EItemCategory::Medical"},
        {
            "CodeName": "R",
            "DisplayName": "Rifle",
            "DisplayNameLocales": {"ru": "Винтовка"},
            "ItemCategory": "EItemCategory::SmallArms",
        },
    ]
    path.write_text(json.dumps(entries), encoding="utf-8")
    items = [{"code": "A", "quantity": 1}, {"code": "R", "quantity": 2}]

    pages = build_pages(
        stockpile=Stockpile.model_validate({"items": items}),
        catalog=_text("ru", catalog=CatalogService(catalog_path=path)),
    )

    texts = [line.text for line in pages[0].columns[0]]
    expected = _texts("ru")["categories"]
    assert texts == [expected["small_arms"], "Винтовка", expected["medical"], "Aid"]


def test_the_type_placeholder_is_in_the_language_of_the_output() -> None:
    """And the name of the type, not its code."""
    filled = fill_stockpile_text(
        settings=ImageHandlerSettings(language="de"),
        template="{type}: {name}",
        stockpile=Stockpile(name="Depot", type=StockpileType.ENCAMPMENT),
    )

    assert filled == "Feldlager: Depot"


def test_the_merge_of_stockpiles_is_named_in_the_language_of_the_output() -> None:
    """It is the title of the image."""
    groups = group_stockpiles(
        settings=ImageHandlerSettings(language="es", grouping=StockpileGrouping.ALL),
        stockpiles=[Stockpile(name="A"), Stockpile(name="B")],
    )

    assert groups[0].drawn.name == _texts("es")["all_stockpiles"]


def test_drawing_uses_the_language_of_the_settings() -> None:
    """The renderer receives its texts."""
    with (
        patch.object(rendering, "StockpileImageRenderer") as renderer,
        patch.object(rendering, "load_icons", return_value={}),
    ):
        rendering.render_stockpile(
            settings=ImageHandlerSettings(language="de"), stockpile=Stockpile(name="A")
        )

    assert renderer.call_args.kwargs["text"].no_items() == _texts("de")["no_items"]
