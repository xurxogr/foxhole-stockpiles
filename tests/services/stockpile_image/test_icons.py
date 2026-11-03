"""The item icons of the template database."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from foxhole_stockpiles.services.stockpile_image import icons
from foxhole_stockpiles.services.stockpile_image.icons import list_icon_mods, load_icons

_DB = Path("db.h5")


def _template(code: str, mod: str, crated: bool = False, size: int = 32) -> dict[str, Any]:
    # Blue in BGR order, with a different value per mod.
    blue = 200 if mod == "vanilla" else 100
    return {
        "code": code,
        "mod_name": mod,
        "crated": crated,
        "size": size,
        "image": bytes([blue, 0, 0]) * (size * size),
    }


def _load(mod: str, templates: list[dict[str, Any]]) -> dict[tuple[str, bool], Any]:
    with (
        patch(f"{icons.__name__}.fs_assets.database_statistics") as statistics,
        patch(f"{icons.__name__}.fs_assets.read_templates", return_value=templates),
    ):
        statistics.return_value = {"resolutions": [1080], "mods": {}}
        return load_icons(database_path=_DB, mod=mod)


def test_icon_is_found_by_code_and_crate_state() -> None:
    """A crate has its own icon."""
    loaded = _load("vanilla", [_template("a", "vanilla"), _template("a", "vanilla", crated=True)])

    assert set(loaded) == {("a", False), ("a", True)}


def test_colors_are_converted_from_the_order_of_the_database() -> None:
    """The database stores BGR, and an image is drawn in RGB."""
    loaded = _load("vanilla", [_template("a", "vanilla")])

    assert loaded[("a", False)].getpixel((0, 0)) == (0, 0, 200)


def test_chosen_mod_replaces_the_base_game_icon() -> None:
    """An item changed by the mod shows the icon of the mod."""
    loaded = _load("mymod", [_template("a", "vanilla"), _template("a", "mymod")])

    assert loaded[("a", False)].getpixel((0, 0)) == (0, 0, 100)


def test_item_the_mod_does_not_change_keeps_the_base_game_icon() -> None:
    """A mod usually holds only part of the items."""
    loaded = _load("mymod", [_template("a", "vanilla"), _template("b", "mymod")])

    assert loaded[("a", False)].getpixel((0, 0)) == (0, 0, 200)


def test_icons_of_other_mods_are_ignored() -> None:
    """A database can hold several mods."""
    loaded = _load("vanilla", [_template("a", "othermod")])

    assert loaded == {}


def test_icons_are_scaled_to_the_row_size() -> None:
    """A database without the usual resolution still gives icons that fit."""
    loaded = _load("vanilla", [_template("a", "vanilla", size=64)])

    assert loaded[("a", False)].size == (icons.ICON_SIZE, icons.ICON_SIZE)


def test_closest_resolution_is_read() -> None:
    """A database may have been built with only some resolutions."""
    with (
        patch(f"{icons.__name__}.fs_assets.database_statistics") as statistics,
        patch(f"{icons.__name__}.fs_assets.read_templates", return_value=[]) as read,
    ):
        statistics.return_value = {"resolutions": [720, 1200, 2160], "mods": {}}
        load_icons(database_path=_DB, mod="vanilla")

    assert read.call_args.kwargs["resolution"] == 1200


def test_no_database_means_no_icons() -> None:
    """The image is still produced, with text only."""
    assert load_icons(database_path=None, mod="vanilla") == {}


def test_unreadable_database_means_no_icons() -> None:
    """A broken database does not stop the image."""
    with patch(f"{icons.__name__}.fs_assets.database_statistics", side_effect=ValueError("bad")):
        assert load_icons(database_path=_DB, mod="vanilla") == {}


def test_a_broken_template_is_skipped() -> None:
    """One bad record does not lose the other icons."""
    bad = {**_template("bad", "vanilla"), "image": b"short"}

    assert set(_load("vanilla", [bad, _template("a", "vanilla")])) == {("a", False)}


def test_mods_of_a_database_are_listed() -> None:
    """The settings can offer them."""
    with patch(f"{icons.__name__}.fs_assets.database_statistics") as statistics:
        statistics.return_value = {"resolutions": [], "mods": {"vanilla": {}, "mymod": {}}}

        assert list_icon_mods(_DB) == ["mymod", "vanilla"]


def test_mods_of_a_missing_database_are_none() -> None:
    """Nothing can be offered without it."""
    assert list_icon_mods(None) == []
    with patch(f"{icons.__name__}.fs_assets.database_statistics", side_effect=OSError("gone")):
        assert list_icon_mods(_DB) == []
