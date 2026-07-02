"""Webhook output handler - sends data to webhook endpoint."""

import logging
from typing import Any

from foxhole_stockpiles.connectors.webhook import WebhookConnector
from foxhole_stockpiles.core.settings.sections.output import WebhookHandlerSettings
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.stockpile_json import stockpiles_to_json_payload
from foxhole_stockpiles.models.stockpile import Stockpile


class WebhookOutputHandler(BaseOutputDestinationHandler):
    """Handles sending stockpile data to webhook endpoints."""

    def __init__(self, webhook_settings: WebhookHandlerSettings) -> None:
        """Initialize webhook output handler.

        Args:
            webhook_settings (WebhookHandlerSettings): Webhook configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self._url = webhook_settings.url
        self._webhook_connector = WebhookConnector(webhook_settings)

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> list[str]:
        """Send stockpile data to webhook endpoint.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to send
            **kwargs: Additional parameters:
                - token (str | None): Optional auth token to override configured token

        Returns:
            list[str]: The webhook response message(s).
        """
        if not self._url:
            return ["URL not configured"]

        payload = stockpiles_to_json_payload(stockpiles)
        token = kwargs.get("token")

        response = await self._webhook_connector.send_stockpile(payload=payload, token=token)
        self.logger.debug("Webhook response: %s", response)
        return response
