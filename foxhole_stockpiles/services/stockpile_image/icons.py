"""Read the item icons from the template database."""

import logging
from pathlib import Path
from typing import Final

import fs_assets
from PIL import Image

logger = logging.getLogger(__name__)

ICON_SIZE: Final[int] = 32
BASE_GAME_MOD: Final[str] = "vanilla"

# The icons of this resolution have the size of a row, so they need no scaling.
_PREFERRED_RESOLUTION: Final[int] = 1080
# What fs-assets raises for a database it cannot read.
_DATABASE_ERRORS: Final = (OSError, ValueError, RuntimeError)

IconKey = tuple[str, bool]


def _to_image(data: bytes, size: int) -> Image.Image:
    """Convert a stored icon to an image of the size of a row.

    Args:
        data (bytes): Its pixels, row by row, in BGR order.
        size (int): The side of the stored icon.

    Returns:
        Image.Image: The icon in RGB.
    """
    image = Image.frombytes("RGB", (size, size), data, "raw", "BGR")
    if size == ICON_SIZE:
        return image
    return image.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)


def load_icons(database_path: Path | None, mod: str) -> dict[IconKey, Image.Image]:
    """Read the icons of the base game, with those of a mod replacing them.

    Args:
        database_path (Path | None): The template database, if there is one.
        mod (str): The mod whose icons are preferred.

    Returns:
        dict[IconKey, Image.Image]: The icon of each (code, crated). Empty if the
            database cannot be read: the image is then drawn with text only.
    """
    if database_path is None:
        return {}
    try:
        resolutions = fs_assets.database_statistics(str(database_path))["resolutions"]
        resolution = min(resolutions, key=lambda value: abs(value - _PREFERRED_RESOLUTION))
        templates = fs_assets.read_templates(str(database_path), resolution=resolution)
    except _DATABASE_ERRORS as e:
        logger.warning("Could not read the icons of the database: %s", e)
        return {}

    icons: dict[IconKey, Image.Image] = {}
    # The base game first, so that the icons of the mod replace it.
    for wanted in (BASE_GAME_MOD, mod):
        for template in templates:
            if template["mod_name"] != wanted:
                continue
            try:
                icon = _to_image(data=template["image"], size=template["size"])
            except ValueError as e:
                logger.warning("Skipping the icon of %s: %s", template["code"], e)
                continue
            icons[(template["code"], template["crated"])] = icon
    return icons


def list_icon_mods(database_path: Path | None) -> list[str]:
    """List the mods of a template database.

    Args:
        database_path (Path | None): The template database, if there is one.

    Returns:
        list[str]: Their names, empty if the database cannot be read.
    """
    if database_path is None:
        return []
    try:
        return sorted(fs_assets.database_statistics(str(database_path))["mods"])
    except _DATABASE_ERRORS as e:
        logger.warning("Could not read the mods of the database: %s", e)
        return []
