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


def test_headline_template_is_filled_with_the_stockpile() -> None:
    """The drawing gets the final text."""
    renderer, _ = _render(ImageHandlerSettings(headline="Report {name}"))

    assert renderer.return_value.render_png.call_args.kwargs["headline"] == "Report Depot"


def test_empty_headline_counts_as_unset() -> None:
    """The title falls back to the name of the stockpile."""
    renderer, _ = _render(ImageHandlerSettings(headline="   "))

    assert renderer.return_value.render_png.call_args.kwargs["headline"] is None


def test_icons_of_the_chosen_mod_come_from_the_scanner_database(monkeypatch: Any) -> None:
    """The mod is of the handler, and the database of the whole application."""
    monkeypatch.setenv("FS_SCANNER__DATABASE_PATH", str(Path("db.h5")))
    rendering.get_settings.cache_clear()

    _, icons = _render(ImageHandlerSettings(icon_mod="mymod"))

    assert icons.call_args.kwargs == {"database_path": Path("db.h5"), "mod": "mymod"}
