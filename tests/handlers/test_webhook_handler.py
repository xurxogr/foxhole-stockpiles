"""Tests for handlers.webhook module."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from foxhole_stockpiles.core.settings.sections.output import WebhookHandlerSettings
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.handlers.webhook import WebhookOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem


@pytest.fixture
def webhook_settings() -> WebhookHandlerSettings:
    """Create webhook settings for testing."""
    return WebhookHandlerSettings(url="https://example.com/webhook")


@pytest.fixture
def sample_stockpile() -> Stockpile:
    """Create a sample stockpile for testing."""
    return Stockpile(
        name="TestStockpile",
        type=StockpileType.SEAPORT,
        items=[
            StockpileItem(code="Rifle", quantity=100, crated=False, confidence=0.95),
        ],
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
    )


class TestWebhookOutputHandlerInit:
    """Test suite for WebhookOutputHandler initialization."""

    def test_init_with_settings(self, webhook_settings: WebhookHandlerSettings) -> None:
        """Test initialization with settings."""
        handler = WebhookOutputHandler(webhook_settings)
        assert handler._url == "https://example.com/webhook"


class TestWebhookOutputHandlerHandle:
    """Test suite for WebhookOutputHandler.handle method."""

    @pytest.mark.asyncio
    async def test_handle_single_stockpile(
        self, webhook_settings: WebhookHandlerSettings, sample_stockpile: Stockpile
    ) -> None:
        """Test handling a single stockpile."""
        handler = WebhookOutputHandler(webhook_settings)

        with patch.object(
            handler._webhook_connector, "send_stockpile", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = ["ok"]

            result = await handler.handle([sample_stockpile])

            assert result == ["ok"]
            mock_send.assert_called_once()
            # Always wrapped in stockpiles array
            call_args = mock_send.call_args
            payload = call_args.kwargs["payload"]
            assert "stockpiles" in payload
            assert len(payload["stockpiles"]) == 1
            assert payload["stockpiles"][0]["name"] == "TestStockpile"

    @pytest.mark.asyncio
    async def test_handle_with_token(
        self, webhook_settings: WebhookHandlerSettings, sample_stockpile: Stockpile
    ) -> None:
        """Test handling with custom token."""
        handler = WebhookOutputHandler(webhook_settings)

        with patch.object(
            handler._webhook_connector, "send_stockpile", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = ["ok"]

            await handler.handle([sample_stockpile], token="custom-token")

            call_args = mock_send.call_args
            assert call_args.kwargs["token"] == "custom-token"

    @pytest.mark.asyncio
    async def test_handle_multiple_stockpiles(
        self, webhook_settings: WebhookHandlerSettings, sample_stockpile: Stockpile
    ) -> None:
        """Test handling multiple stockpiles."""
        handler = WebhookOutputHandler(webhook_settings)

        stockpile2 = Stockpile(
            name="Second",
            type=StockpileType.STORAGE_DEPOT,
            items=[],
            timestamp=datetime.now(tz=UTC),
        )

        with patch.object(
            handler._webhook_connector, "send_stockpile", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = ["ok"]

            result = await handler.handle([sample_stockpile, stockpile2])

            assert result == ["ok"]
            call_args = mock_send.call_args
            payload = call_args.kwargs["payload"]
            assert "stockpiles" in payload
            assert len(payload["stockpiles"]) == 2
            assert payload["stockpiles"][0]["name"] == "TestStockpile"
            assert payload["stockpiles"][1]["name"] == "Second"

    @pytest.mark.asyncio
    async def test_handle_no_url(self, sample_stockpile: Stockpile) -> None:
        """Test handling with no URL configured returns message."""
        settings = WebhookHandlerSettings(url="")
        handler = WebhookOutputHandler(settings)

        result = await handler.handle([sample_stockpile])

        assert result == ["URL not configured"]
