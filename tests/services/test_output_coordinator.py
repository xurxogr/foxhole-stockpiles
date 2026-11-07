"""Tests for output coordinator module.

This module contains comprehensive tests for the OutputCoordinator which orchestrates
output handling by delegating to configured handlers.
"""

from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    ReturnHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.public_stockpile_filter import PublicStockpileFilter
from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator


@pytest.fixture
def sample_stockpile() -> Stockpile:
    """Create a sample stockpile for testing.

    Returns:
        Stockpile: A configured stockpile instance with test data for output testing.
    """
    items = [
        StockpileItem(quantity=100, code="BasicMaterialsIcon", confidence=0.95),
        StockpileItem(quantity=50, code="PetrolIcon", confidence=0.87),
        StockpileItem(quantity=75, code="DieselIcon", confidence=0.92),
    ]

    return Stockpile(
        name="Test Stockpile",
        type=StockpileType.SEAPORT,
        items=items,
        shard="TEST",
        ingame_timestamp="Day 1,000, 1000 Hours",
        resolution="1920x1080",
    )


class TestOutputCoordinator:
    """Test cases for OutputCoordinator."""

    def test_output_coordinator_initialization(self) -> None:
        """Test output coordinator initialization with handlers."""
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="API Response",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                )
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        assert isinstance(coordinator, OutputCoordinator)
        assert coordinator.output_settings is not None
        assert len(coordinator.output_settings.handlers) == 1

    @pytest.mark.asyncio
    async def test_handle_output_return(self, sample_stockpile: Stockpile) -> None:
        """Test RETURN handler processing.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="API Response",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                )
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        result = await coordinator.handle_output([sample_stockpile])

        # Should return dict with stockpiles list from the return handler
        assert isinstance(result, dict)
        assert "stockpiles" in result
        assert len(result["stockpiles"]) == 1
        assert result["stockpiles"][0]["name"] == "Test Stockpile"
        assert result["stockpiles"][0]["type"] == "Seaport"
        assert len(result["stockpiles"][0]["items"]) == 3

    @pytest.mark.asyncio
    async def test_handle_output_file(self, sample_stockpile: Stockpile) -> None:
        """Test FILE handler processing.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="File Output",
                    format=JsonFormatSettings(),
                    handler=FileHandlerSettings(path="output.json"),
                )
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        with patch("foxhole_stockpiles.handlers.file.FileOutputHandler.handle") as mock_handle:
            mock_handle.return_value = None

            result = await coordinator.handle_output([sample_stockpile])

            # No return handler configured, should return None
            assert result is None

    @pytest.mark.asyncio
    async def test_handle_output_multiple_handlers(self, sample_stockpile: Stockpile) -> None:
        """Test multiple handler processing.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="API Response",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                ),
                OutputHandlerConfig(
                    name="File Backup",
                    format=JsonFormatSettings(),
                    handler=FileHandlerSettings(path="backup.json"),
                ),
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        with patch("foxhole_stockpiles.handlers.file.FileOutputHandler.handle") as mock_file_handle:
            mock_file_handle.return_value = None

            result = await coordinator.handle_output([sample_stockpile])

            # Should return result from the return handler
            assert isinstance(result, dict)
            assert "stockpiles" in result
            assert result["stockpiles"][0]["name"] == "Test Stockpile"
            # File handler should also be called
            mock_file_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_output_no_handlers(self, sample_stockpile: Stockpile) -> None:
        """Test with no handlers configured.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(handlers=[])
        coordinator = OutputCoordinator(output_settings=output_settings)

        result = await coordinator.handle_output([sample_stockpile])

        # No handlers, should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_output_webhook_with_token(self, sample_stockpile: Stockpile) -> None:
        """Test WEBHOOK handler with token passes through response.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="Webhook",
                    format=JsonFormatSettings(),
                    handler=WebhookHandlerSettings(
                        url="https://example.com/webhook",
                        auth_type=AuthType.BEARER,
                        token="test-token",
                    ),
                )
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        with patch(
            "foxhole_stockpiles.handlers.webhook.WebhookOutputHandler.handle"
        ) as mock_handle:
            mock_handle.return_value = {"status": "success"}

            result = await coordinator.handle_output([sample_stockpile], token="override-token")

            mock_handle.assert_called_once_with(
                stockpiles=[sample_stockpile], token="override-token"
            )
            # Webhook response is now passed through to caller
            assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_handle_output_handler_error_continues(self, sample_stockpile: Stockpile) -> None:
        """Test that handler errors don't stop other handlers.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="Failing Handler",
                    format=JsonFormatSettings(),
                    handler=ConsoleHandlerSettings(),
                ),
                OutputHandlerConfig(
                    name="API Response",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                ),
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        with patch(
            "foxhole_stockpiles.handlers.console.ConsoleOutputHandler.handle"
        ) as mock_console:
            mock_console.side_effect = Exception("Handler failed")

            # Should still return result from return handler even though console failed
            result = await coordinator.handle_output([sample_stockpile])

            assert isinstance(result, dict)
            assert "stockpiles" in result
            assert result["stockpiles"][0]["name"] == "Test Stockpile"

    @pytest.mark.asyncio
    async def test_return_handler_takes_precedence(self, sample_stockpile: Stockpile) -> None:
        """Test that first return handler result is used.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="First Return",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                ),
                OutputHandlerConfig(
                    name="Second Return",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                ),
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        result = await coordinator.handle_output([sample_stockpile])

        # First return handler result is used
        assert isinstance(result, dict)
        assert "stockpiles" in result
        assert result["stockpiles"][0]["name"] == "Test Stockpile"

    @pytest.mark.asyncio
    async def test_webhook_first_returns_webhook_response(
        self, sample_stockpile: Stockpile
    ) -> None:
        """Test that webhook response is returned when webhook is first.

        When webhook handler is configured before return handler, the webhook's
        response should be passed through to the client.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="Webhook First",
                    format=JsonFormatSettings(),
                    handler=WebhookHandlerSettings(
                        url="https://example.com/webhook",
                    ),
                ),
                OutputHandlerConfig(
                    name="Return Handler",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                ),
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        with patch(
            "foxhole_stockpiles.handlers.webhook.WebhookOutputHandler.handle"
        ) as mock_webhook:
            mock_webhook.return_value = {"webhook": "response", "processed": True}

            result = await coordinator.handle_output([sample_stockpile])

            # Webhook response is used because it's first
            assert result == {"webhook": "response", "processed": True}

    @pytest.mark.asyncio
    async def test_return_first_ignores_webhook_response(self, sample_stockpile: Stockpile) -> None:
        """Test that return handler response is used when it's first.

        When return handler is configured before webhook handler, the return
        handler's response should be passed through (webhook response ignored).

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="Return Handler",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                ),
                OutputHandlerConfig(
                    name="Webhook Second",
                    format=JsonFormatSettings(),
                    handler=WebhookHandlerSettings(
                        url="https://example.com/webhook",
                    ),
                ),
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        with patch(
            "foxhole_stockpiles.handlers.webhook.WebhookOutputHandler.handle"
        ) as mock_webhook:
            mock_webhook.return_value = {"webhook": "response"}

            result = await coordinator.handle_output([sample_stockpile])

            # Return handler response is used because it's first
            assert isinstance(result, dict)
            assert "stockpiles" in result
            assert result["stockpiles"][0]["name"] == "Test Stockpile"
            assert "webhook" not in result

    @pytest.mark.asyncio
    async def test_handle_output_multiple_stockpiles(self, sample_stockpile: Stockpile) -> None:
        """Test handling multiple stockpiles at once.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        # Create a second stockpile
        second_stockpile = Stockpile(
            name="Second Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[
                StockpileItem(quantity=200, code="SulfurIcon", confidence=0.99),
            ],
            shard="TEST",
            resolution="1920x1080",
        )

        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="API Response",
                    format=JsonFormatSettings(),
                    handler=ReturnHandlerSettings(),
                )
            ]
        )
        coordinator = OutputCoordinator(output_settings=output_settings)

        result = await coordinator.handle_output([sample_stockpile, second_stockpile])

        # Should return both stockpiles
        assert isinstance(result, dict)
        assert "stockpiles" in result
        assert len(result["stockpiles"]) == 2
        assert result["stockpiles"][0]["name"] == "Test Stockpile"
        assert result["stockpiles"][1]["name"] == "Second Stockpile"


class _SendsOnlyTheFirst(BaseOutputDestinationHandler):
    """Delivers the first stockpile of each batch and fails on the rest."""

    def __init__(self) -> None:
        self.received: list[list[str]] = []
        self._rest: list[Stockpile] = []

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> None:
        self.received.append([stockpile.name for stockpile in stockpiles])
        self._rest = stockpiles[1:]

    def undelivered(self, batch: list[Stockpile]) -> list[Stockpile]:
        return self._rest


@pytest.mark.asyncio
async def test_only_what_did_not_arrive_is_sent_again() -> None:
    """A retry does not repeat the stockpiles a handler did deliver."""
    handler = _SendsOnlyTheFirst()
    coordinator = OutputCoordinator(OutputSettings(handlers=[OutputHandlerConfig(name="partial")]))
    first, second, third = (Stockpile(name=name) for name in "ABC")

    with patch.object(coordinator, "_create_handler", return_value=handler):
        await coordinator.handle_output(stockpiles=[first, second])
        await coordinator.handle_output(stockpiles=[third])

    assert handler.received == [["A", "B"], ["B", "C"]]


class _Records(BaseOutputDestinationHandler):
    """Keeps what it receives, and fails to deliver it while told to."""

    def __init__(self, fails: bool = False) -> None:
        self.received: list[list[Stockpile]] = []
        self.fails = fails

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> None:
        self.received.append(stockpiles)

    def undelivered(self, batch: list[Stockpile]) -> list[Stockpile]:
        return batch if self.fails else []


def _seaport(name: str, quantity: int = 1) -> Stockpile:
    return Stockpile(
        name=name,
        type=StockpileType.SEAPORT,
        hex="WestgateHex",
        is_reserve=name != "Public",
        items=[StockpileItem(code="Rifle", quantity=quantity)],
    )


@pytest.mark.asyncio
async def test_each_handler_receives_the_public_stockpiles_it_asks_for() -> None:
    """One output can leave them out while another receives everything."""
    everything, reserves = _Records(), _Records()
    coordinator = OutputCoordinator(
        OutputSettings(
            handlers=[
                OutputHandlerConfig(name="all"),
                OutputHandlerConfig(name="reserves", public_stockpiles=PublicStockpileFilter.NONE),
            ]
        )
    )
    public, reserve = _seaport("Public"), _seaport("Reserve")

    with patch.object(coordinator, "_create_handler", side_effect=[everything, reserves]):
        await coordinator.handle_output(stockpiles=[public, reserve])

    assert everything.received == [[public, reserve]]
    assert reserves.received == [[reserve]]


@pytest.mark.asyncio
async def test_a_handler_receives_its_stockpiles_grouped() -> None:
    """Grouped by hex, both stockpiles arrive as one."""
    handler = _Records()
    config = OutputHandlerConfig(name="grouped", grouping=StockpileGrouping.HEX)
    coordinator = OutputCoordinator(OutputSettings(handlers=[config]))

    with patch.object(coordinator, "_create_handler", return_value=handler):
        await coordinator.handle_output(stockpiles=[_seaport("A", 2), _seaport("B", 3)])

    (merged,) = handler.received[0]
    assert merged.name == "Westgate"
    assert merged.items[0].quantity == 5


@pytest.mark.asyncio
async def test_an_undelivered_merge_is_sent_again_from_its_stockpiles() -> None:
    """A newer version of a stockpile replaces the old one instead of adding up twice."""
    handler = _Records(fails=True)
    config = OutputHandlerConfig(name="grouped", grouping=StockpileGrouping.ALL)
    coordinator = OutputCoordinator(OutputSettings(handlers=[config]))

    with patch.object(coordinator, "_create_handler", return_value=handler):
        await coordinator.handle_output(stockpiles=[_seaport("A", 2), _seaport("B", 3)])
        handler.fails = False
        await coordinator.handle_output(stockpiles=[_seaport("A", 10)])
        await coordinator.handle_output(stockpiles=[_seaport("C", 1)])

    totals = [[stockpile.items[0].quantity for stockpile in batch] for batch in handler.received]
    assert totals == [[5], [13], [1]]
