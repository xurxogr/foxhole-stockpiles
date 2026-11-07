"""The output handler that saves stockpiles as images."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PIL import Image

from foxhole_stockpiles.core.settings.sections.output import (
    ImageHandlerSettings,
    OutputHandlerConfig,
    OutputSettings,
)
from foxhole_stockpiles.handlers import image as image_module
from foxhole_stockpiles.handlers.image import ImageOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator


def _stockpile(name: str = "Depot") -> Stockpile:
    return Stockpile(name=name, items=[StockpileItem(code="Rifle", quantity=5)])


def _handler(path: Path, **settings: Any) -> ImageOutputHandler:
    return ImageOutputHandler(ImageHandlerSettings(path=str(path), **settings))


@pytest.mark.asyncio
async def test_a_stockpile_is_saved_as_a_png(tmp_path: Path) -> None:
    """The file can be opened as an image."""
    target = tmp_path / "out" / "{stockpile_name}.png"

    await _handler(target).handle([_stockpile()])

    with Image.open(tmp_path / "out" / "Depot.png") as image:
        assert image.format == "PNG"


@pytest.mark.asyncio
async def test_extension_is_always_png(tmp_path: Path) -> None:
    """A path with another extension does not hide what the file is."""
    await _handler(tmp_path / "shot.json").handle([_stockpile()])

    assert (tmp_path / "shot.png").exists()


@pytest.mark.asyncio
async def test_each_stockpile_gets_its_own_file(tmp_path: Path) -> None:
    """Placeholders apply to each stockpile."""
    await _handler(tmp_path / "{stockpile_name}.png").handle([_stockpile("a"), _stockpile("b")])

    assert {path.name for path in tmp_path.iterdir()} == {"a.png", "b.png"}


@pytest.mark.asyncio
async def test_stockpiles_with_the_same_path_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """A template without the name still keeps every image of a batch."""
    await _handler(tmp_path / "shot.png").handle([_stockpile("a"), _stockpile("b")])

    assert {path.name for path in tmp_path.iterdir()} == {"shot.png", "shot_2.png"}


@pytest.mark.asyncio
async def test_each_page_gets_its_own_file(tmp_path: Path) -> None:
    """A stockpile too long for one image is not cut."""
    pages = [b"one", b"two"]
    with patch.object(image_module, "render_stockpile", return_value=pages):
        await _handler(tmp_path / "shot.png").handle([_stockpile()])

    assert (tmp_path / "shot.png").read_bytes() == b"one"
    assert (tmp_path / "shot_2.png").read_bytes() == b"two"


@pytest.mark.asyncio
async def test_name_of_a_stockpile_cannot_leave_the_folder(tmp_path: Path) -> None:
    """Names come from the game, where others write them."""
    target = tmp_path / "out" / "{stockpile_name}.png"

    await _handler(target).handle([_stockpile("../../evil")])

    assert [path.name for path in (tmp_path / "out").iterdir()] == ["_.._evil.png"]


@pytest.mark.asyncio
async def test_no_stockpiles_write_nothing(tmp_path: Path) -> None:
    """There is nothing to draw."""
    await _handler(tmp_path / "shot.png").handle([])

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_a_failed_write_is_retried_with_the_next_batch(tmp_path: Path) -> None:
    """The coordinator keeps what could not be saved."""
    blocked = tmp_path / "file"
    blocked.write_text("not a directory", encoding="utf-8")
    config = OutputHandlerConfig(
        name="image", handler=ImageHandlerSettings(path=str(blocked / "shot.png"))
    )
    coordinator = OutputCoordinator(OutputSettings(handlers=[config]))

    await coordinator.handle_output([_stockpile()])

    assert coordinator._undelivered[0]


def test_settings_load_from_json_with_their_type() -> None:
    """The handler type selects these settings."""
    config = OutputHandlerConfig.model_validate(
        {"name": "image", "handler": {"type": "image", "path": "a.png", "icon_mod": "mymod"}}
    )

    assert isinstance(config.handler, ImageHandlerSettings)
    assert config.handler.icon_mod == "mymod"


def test_base_game_icons_are_used_by_default() -> None:
    """Nothing needs to be set to get icons."""
    assert ImageHandlerSettings().icon_mod == "vanilla"


def test_unknown_setting_is_refused() -> None:
    """A typo in the configuration is reported."""
    with pytest.raises(ValueError, match="nope"):
        ImageHandlerSettings.model_validate({"nope": 1})
