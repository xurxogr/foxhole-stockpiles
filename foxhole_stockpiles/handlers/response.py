"""Return output handler - returns data to caller."""

import logging
from typing import Any

from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.stockpile_json import stockpiles_to_json_payload
from foxhole_stockpiles.models.stockpile import Stockpile


class ReturnOutputHandler(BaseOutputDestinationHandler):
    """Handles returning stockpile data to the caller (API/CLI)."""

    def __init__(self) -> None:
        """Initialize return output handler."""
        self.logger = logging.getLogger(__name__)

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> dict[str, Any]:
        """Return stockpile data as JSON dictionary.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to return
            **kwargs: Additional parameters (unused)

        Returns:
            dict[str, Any]: Stockpile data as JSON dictionary with {"stockpiles": [...]}
        """
        self.logger.debug("Returning stockpile data to caller")
        return stockpiles_to_json_payload(stockpiles)
