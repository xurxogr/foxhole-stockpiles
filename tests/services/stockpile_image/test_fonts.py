"""Which font draws each text."""

from pathlib import Path
from typing import Any

import pytest
from PIL import ImageFont

from foxhole_stockpiles.services.stockpile_image import fonts
from foxhole_stockpiles.services.stockpile_image.font_selector import FontSelector


def test_without_any_font_the_bundled_one_draws_the_text(monkeypatch: Any) -> None:
    """An image can always be produced."""
    monkeypatch.setattr(fonts, "SYSTEM_FONTS", ())

    font = FontSelector().font_for(text="Rifle", size=20)

    assert font.getlength("Rifle") > 0


def test_bundled_font_is_known_not_to_cover_chinese() -> None:
    """Covering is checked per character, as drawing them would show squares."""
    font = ImageFont.load_default(size=20)

    assert fonts.covers(font=font, text="Rifle")
    assert not fonts.covers(font=font, text="中")


def test_spaces_do_not_count_as_missing_characters() -> None:
    """They have no shape in any font."""
    assert fonts.covers(font=ImageFont.load_default(size=20), text=" \t")


def test_unreadable_configured_font_is_ignored(monkeypatch: Any, tmp_path: Path) -> None:
    """A wrong path in the settings does not stop the image."""
    monkeypatch.setattr(fonts, "SYSTEM_FONTS", ())
    bad = tmp_path / "bad.ttf"
    bad.write_bytes(b"not a font")

    font = FontSelector(font_path=str(bad)).font_for(text="Rifle", size=20)

    assert font.getlength("Rifle") > 0


def test_first_font_covering_the_text_is_chosen(monkeypatch: Any) -> None:
    """Latin text keeps its font while Chinese text finds one that has it."""
    regular = ImageFont.load_default(size=20)
    chinese = ImageFont.load_default(size=21)
    monkeypatch.setattr(fonts, "SYSTEM_FONTS", ("latin.ttf", "chinese.ttf"))
    monkeypatch.setattr(
        fonts,
        "load_font",
        lambda path, size: {"latin.ttf": regular, "chinese.ttf": chinese}[path],
    )
    monkeypatch.setattr(fonts, "covers", lambda font, text: font is chinese or text.isascii())
    selector = FontSelector()

    assert selector.font_for(text="Rifle", size=20) is regular
    assert selector.font_for(text="中文", size=20) is chinese


def test_text_no_font_covers_uses_the_first_available_font(monkeypatch: Any) -> None:
    """It is drawn as well as it can be, and the rest of the image is fine."""
    regular = ImageFont.load_default(size=20)
    monkeypatch.setattr(fonts, "SYSTEM_FONTS", ("latin.ttf",))
    monkeypatch.setattr(fonts, "load_font", lambda path, size: regular)
    monkeypatch.setattr(fonts, "covers", lambda font, text: False)

    assert FontSelector().font_for(text="中", size=20) is regular


def test_load_font_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    """Most of the known fonts are not on a given system."""
    assert fonts.load_font(path=str(tmp_path / "missing.ttf"), size=20) is None


@pytest.mark.parametrize("path", ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"])
def test_windows_fonts_for_all_the_interface_languages_are_tried(path: str) -> None:
    """Latin, Cyrillic and Chinese are covered on a stock Windows."""
    assert path in fonts.SYSTEM_FONTS
