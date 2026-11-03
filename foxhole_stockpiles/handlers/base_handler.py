"""Base output destination handler interface."""

from abc import ABC, abstractmethod
from typing import Any

from foxhole_stockpiles.models.stockpile import Stockpile


class BaseOutputDestinationHandler(ABC):
    """Abstract base class for output destination handlers.

    Attributes:
        delivered (bool): False after ``handle`` when the data did not reach the
            destination but the failure was reported through its response instead
            of raising. The batch is then sent again with the next one.
    """

    delivered: bool = True

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

    def undelivered(self, batch: list[Stockpile]) -> list[Stockpile]:
        """Tell which stockpiles of a batch did not reach the destination.

        A handler that sends them one by one overrides this, so a retry does not
        repeat the ones that did arrive.

        Args:
            batch (list[Stockpile]): What ``handle`` received.

        Returns:
            list[Stockpile]: The ones to send again with the next batch.
        """
        return [] if self.delivered else batch

    async def close(self) -> None:  # noqa: B027 - optional hook, most handlers hold nothing
        """Release the resources of this handler. Nothing to release by default."""
