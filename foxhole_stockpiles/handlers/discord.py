"""Discord output handler - posts stockpiles as images to a webhook."""

import asyncio
import logging
from typing import Any

from foxhole_stockpiles.connectors.discord import DiscordConnector
from foxhole_stockpiles.core.settings.sections.output.discord_handler import (
    DiscordHandlerSettings,
    is_discord_webhook_url,
)
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_image.aggregation import stockpiles_to_draw
from foxhole_stockpiles.services.stockpile_image.placeholders import fill_template
from foxhole_stockpiles.services.stockpile_image.rendering import render_stockpile

logger = logging.getLogger(__name__)


class DiscordOutputHandler(BaseOutputDestinationHandler):
    """Posts each stockpile as a message with the images of its pages.

    It stops at the first failure, and only what was not posted is sent again.
    """

    def __init__(self, discord_settings: DiscordHandlerSettings) -> None:
        """Initialize the handler.

        Args:
            discord_settings (DiscordHandlerSettings): Where and how to post.
        """
        self._settings = discord_settings
        self._connector = DiscordConnector(
            url=discord_settings.url,
            username=discord_settings.username,
            avatar_url=discord_settings.avatar_url,
        )
        self._undelivered: list[Stockpile] = []

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> list[str] | None:
        """Post some stockpiles.

        Args:
            stockpiles (list[Stockpile]): The stockpiles.
            **kwargs: Not used by this handler.

        Returns:
            list[str] | None: Why they could not all be posted, or None if they were.
        """
        self._undelivered = []
        if not stockpiles:
            logger.warning("No stockpiles to draw, skipping Discord output")
            return None
        if not is_discord_webhook_url(self._settings.url):
            self._undelivered = stockpiles
            return self._report("the URL is not a Discord webhook")

        drawn = stockpiles_to_draw(settings=self._settings, stockpiles=stockpiles)
        for position, stockpile in enumerate(drawn):
            try:
                await self._post(stockpile)
            except Exception as e:  # noqa: BLE001 - what was posted must not be posted again
                self._undelivered = stockpiles if self._settings.aggregate else drawn[position:]
                return self._report(str(e))
        logger.info("Posted %d stockpile(s) to Discord", len(drawn))
        return None

    def undelivered(self, batch: list[Stockpile]) -> list[Stockpile]:
        """Tell which stockpiles were not posted.

        Args:
            batch (list[Stockpile]): What ``handle`` received.

        Returns:
            list[Stockpile]: The ones to send again with the next batch.
        """
        return self._undelivered

    async def close(self) -> None:
        """Close the HTTP client of the connector."""
        await self._connector.close()

    async def _post(self, stockpile: Stockpile) -> None:
        """Draw and post one stockpile.

        Args:
            stockpile (Stockpile): The stockpile.
        """
        pages = await asyncio.to_thread(
            render_stockpile, settings=self._settings, stockpile=stockpile
        )
        message = (self._settings.message or "").strip()
        await self._connector.send_images(
            content=fill_template(template=message, stockpile=stockpile) if message else None,
            images=pages,
        )

    @staticmethod
    def _report(reason: str) -> list[str]:
        """Log why something was not posted.

        Args:
            reason (str): The reason, without the URL.

        Returns:
            list[str]: The message for the user.
        """
        message = f"FS: Could not post to Discord: {reason}"
        logger.error(message)
        return [message]
