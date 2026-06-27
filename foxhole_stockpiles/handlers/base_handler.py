"""Base output destination handler interface."""

from abc import ABC, abstractmethod
from typing import Any

from foxhole_stockpiles.models.stockpile import Stockpile


class BaseOutputDestinationHandler(ABC):
    """Abstract base class for output destination handlers."""

    @abstractmethod
    async def handle(
        self, stockpiles: list[Stockpile], **kwargs: Any
    ) -> dict[str, Any] | list[str] | None:
        """Handle output to the destination.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to output
            **kwargs: Additional destination-specific parameters

        Returns:
            dict[str, Any] | list[str] | None: Optional response data from the
                destination (a dict, a list of messages, or None).
        """
        pass
