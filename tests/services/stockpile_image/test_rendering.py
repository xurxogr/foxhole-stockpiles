"""Drawing a stockpile with the settings of a handler."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from foxhole_stockpiles.core.settings.sections.output import ImageHandlerSettings
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_image import rendering
from foxhole_stockpiles.services.stockpile_image.rendering import render_stockpile

_MODULE = rendering.__name__


def _render(settings: ImageHandlerSettings, stockpile: Stockpile | None = None) -> Any:
    with (
        patch(f"{_MODULE}.StockpileImageRenderer") as renderer,
        patch(f"{_MODULE}.load_icons", return_value={}) as icons,
    ):
        render_stockpile(settings=settings, stockpile=stockpile or Stockpile(name="Depot"))
    return renderer, icons


def test_the_stockpile_is_drawn_as_it_is() -> None:
    """Its title comes from its type and name, not from the headline."""
    stockpile = Stockpile(name="Depot")

    renderer, _ = _render(ImageHandlerSettings(headline="Report {name}"), stockpile=stockpile)

    renderer.return_value.render_png.assert_called_once_with(stockpile)


def test_icons_of_the_chosen_mod_come_from_the_scanner_database(monkeypatch: Any) -> None:
    """The mod is of the handler, and the database of the whole application."""
    monkeypatch.setenv("FS_SCANNER__DATABASE_PATH", str(Path("db.h5")))
    rendering.get_settings.cache_clear()

    _, icons = _render(ImageHandlerSettings(icon_mod="mymod"))

    assert icons.call_args.kwargs == {"database_path": Path("db.h5"), "mod": "mymod"}
