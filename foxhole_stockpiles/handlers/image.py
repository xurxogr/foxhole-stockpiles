"""Image output handler - saves stockpiles as PNG files."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Final

from foxhole_stockpiles.core.settings.sections.output.image_handler import ImageHandlerSettings
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.path_template import fill_path_template, with_extension
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_image.aggregation import stockpiles_to_draw
from foxhole_stockpiles.services.stockpile_image.rendering import render_stockpile

_EXTENSION: Final[str] = ".png"

logger = logging.getLogger(__name__)


def _free_path(path: Path, taken: set[Path]) -> Path:
    """Find a path no other image of the batch has.

    Args:
        path (Path): The path the template gives.
        taken (set[Path]): The paths already used.

    Returns:
        Path: The same path, or with a number before its extension.
    """
    candidate = path
    number = 1
    while candidate in taken:
        number += 1
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
    return candidate


class ImageOutputHandler(BaseOutputDestinationHandler):
    """Saves each stockpile as one PNG per page.

    A failure is raised, so the coordinator keeps the batch for the next send.
    """

    def __init__(self, image_settings: ImageHandlerSettings) -> None:
        """Initialize the handler.

        Args:
            image_settings (ImageHandlerSettings): Where and how to save the images.
        """
        self._settings = image_settings

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> None:
        """Save the images of some stockpiles.

        Args:
            stockpiles (list[Stockpile]): The stockpiles.
            **kwargs: Not used by this handler.
        """
        if not stockpiles:
            logger.warning("No stockpiles to draw, skipping image output")
            return
        await asyncio.to_thread(self._save_all, stockpiles)

    def _save_all(self, stockpiles: list[Stockpile]) -> None:
        """Draw and write the images, outside the event loop.

        Args:
            stockpiles (list[Stockpile]): The stockpiles.
        """
        template = with_extension(path=self._settings.path, extension=_EXTENSION)
        taken: set[Path] = set()
        for stockpile in stockpiles_to_draw(settings=self._settings, stockpiles=stockpiles):
            filled = fill_path_template(template=template, stockpiles=[stockpile])
            pages = render_stockpile(settings=self._settings, stockpile=stockpile)
            for page in pages:
                path = _free_path(path=Path(filled), taken=taken)
                taken.add(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(page)
                logger.debug("Image saved to: %s", path)
