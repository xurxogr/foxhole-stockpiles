"""Tests for individual output handler implementations.

This module contains tests for specific output destination handlers:
ConsoleOutputHandler, ReturnOutputHandler, FileOutputHandler, and WebhookOutputHandler.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from foxhole_stockpiles.core.settings.sections.output import (
    WebhookHandlerSettings,
)
from foxhole_stockpiles.core.settings.sections.output.csv_format import (
    CsvFormatSettings,
)
from foxhole_stockpiles.core.settings.sections.output.json_format import (
    JsonFormatSettings,
)
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.handlers.console import ConsoleOutputHandler
from foxhole_stockpiles.handlers.file import FileOutputHandler
from foxhole_stockpiles.handlers.response import ReturnOutputHandler
from foxhole_stockpiles.handlers.webhook import WebhookOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem


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


class TestConsoleOutputHandler:
    """Test cases for ConsoleOutputHandler."""

    @pytest.mark.asyncio
    async def test_console_output(self, sample_stockpile: Stockpile) -> None:
        """Test console output method.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = ConsoleOutputHandler()

        with patch.object(handler.logger, "info") as mock_logger:
            await handler.handle([sample_stockpile])

            # Verify logger calls
            mock_logger.assert_any_call("Name: %s", "Test Stockpile")
            mock_logger.assert_any_call("Type: %s", "Seaport")
            mock_logger.assert_any_call("Shard: %s", "TEST")

    @pytest.mark.asyncio
    async def test_console_output_with_crated_items(self) -> None:
        """Test console output with crated items appends _crated suffix."""
        items = [
            StockpileItem(
                quantity=100,
                code="BasicMaterialsIcon",
                confidence=0.95,
                crated=True,
            ),
            StockpileItem(
                quantity=50,
                code="PetrolIcon",
                confidence=0.87,
                crated=False,
            ),
        ]

        stockpile = Stockpile(
            name="Test Stockpile",
            type=StockpileType.SEAPORT,
            items=items,
            shard="TEST",
            resolution="1920x1080",
        )

        handler = ConsoleOutputHandler()

        with patch.object(handler.logger, "info") as mock_logger:
            await handler.handle([stockpile])

            # Verify crated item has _crated suffix
            mock_logger.assert_any_call(
                "* code: %-35s quantity: %-3d, confidence: %.3f",
                "BasicMaterialsIcon_crated",
                100,
                0.95,
            )
            # Verify non-crated item doesn't have suffix
            mock_logger.assert_any_call(
                "* code: %-35s quantity: %-3d, confidence: %.3f",
                "PetrolIcon",
                50,
                0.87,
            )

    @pytest.mark.asyncio
    async def test_console_output_multiple_stockpiles(self, sample_stockpile: Stockpile) -> None:
        """Test console output with multiple stockpiles adds separator.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        second_stockpile = Stockpile(
            name="Second Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[StockpileItem(quantity=200, code="SulfurIcon", confidence=0.99)],
            shard="TEST",
            resolution="1920x1080",
        )

        handler = ConsoleOutputHandler()

        with patch.object(handler.logger, "info") as mock_logger:
            await handler.handle([sample_stockpile, second_stockpile])

            # Verify separator between stockpiles
            mock_logger.assert_any_call("---")
            # Verify both stockpiles logged
            mock_logger.assert_any_call("Name: %s", "Test Stockpile")
            mock_logger.assert_any_call("Name: %s", "Second Stockpile")


class TestReturnOutputHandler:
    """Test cases for ReturnOutputHandler."""

    @pytest.mark.asyncio
    async def test_return_output(self, sample_stockpile: Stockpile) -> None:
        """Test return output handler.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = ReturnOutputHandler()
        result = await handler.handle([sample_stockpile])

        assert isinstance(result, dict)
        assert "stockpiles" in result
        assert len(result["stockpiles"]) == 1
        assert result["stockpiles"][0]["name"] == "Test Stockpile"
        assert result["stockpiles"][0]["type"] == "Seaport"
        assert len(result["stockpiles"][0]["items"]) == 3

    @pytest.mark.asyncio
    async def test_return_output_multiple_stockpiles(self, sample_stockpile: Stockpile) -> None:
        """Test return output handler with multiple stockpiles.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        second_stockpile = Stockpile(
            name="Second Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[],
            resolution="1920x1080",
        )

        handler = ReturnOutputHandler()
        result = await handler.handle([sample_stockpile, second_stockpile])

        assert isinstance(result, dict)
        assert "stockpiles" in result
        assert len(result["stockpiles"]) == 2
        assert result["stockpiles"][0]["name"] == "Test Stockpile"
        assert result["stockpiles"][1]["name"] == "Second Stockpile"


class TestFileOutputHandler:
    """Test cases for FileOutputHandler."""

    @pytest.mark.asyncio
    async def test_file_output_default_path(self, sample_stockpile: Stockpile) -> None:
        """Test file output with default path.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = FileOutputHandler(default_file_path="output.json")

        with patch("pathlib.Path.open") as mock_open, patch("pathlib.Path.mkdir"):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            mock_file.write.assert_called_once()
            written_data = mock_file.write.call_args[0][0]
            data = json.loads(written_data)
            assert "stockpiles" in data
            assert data["stockpiles"][0]["name"] == "Test Stockpile"

    @pytest.mark.asyncio
    async def test_file_output_custom_path(self, sample_stockpile: Stockpile) -> None:
        """Test file output with custom path.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = FileOutputHandler()
        custom_path = Path("custom/output.json")

        with patch("pathlib.Path.open") as mock_open, patch("pathlib.Path.mkdir"):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile], file_path=custom_path)

            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_output_with_timestamp(self, sample_stockpile: Stockpile) -> None:
        """Test file output with timestamp placeholder.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = FileOutputHandler(default_file_path="output_{timestamp}.json")

        with (
            patch("pathlib.Path.open") as mock_open,
            patch("pathlib.Path.mkdir"),
            patch("foxhole_stockpiles.handlers.file.datetime") as mock_datetime_module,
        ):
            mock_now = Mock()
            mock_now.strftime.side_effect = lambda fmt: {
                "%Y-%m-%d_%H-%M-%S": "2025-01-24_14-30-52",
                "%Y": "2025",
                "%m": "01",
                "%d": "24",
                "%H": "14",
                "%M": "30",
                "%S": "52",
            }.get(fmt, "")
            mock_datetime_module.datetime.now.return_value = mock_now
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_output_with_date_placeholders(self, sample_stockpile: Stockpile) -> None:
        """Test file output with year/month/day placeholders for folder structure.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = FileOutputHandler(
            default_file_path="{year}-{month}-{day}/stockpile_{hour}{minute}{second}.json"
        )

        with (
            patch("pathlib.Path.open") as mock_open,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("foxhole_stockpiles.handlers.file.datetime") as mock_datetime_module,
        ):
            # Create a mock datetime object
            mock_now = Mock()
            mock_now.strftime.side_effect = lambda fmt: {
                "%Y-%m-%d_%H-%M-%S": "2025-01-24_14-30-52",
                "%Y": "2025",
                "%m": "01",
                "%d": "24",
                "%H": "14",
                "%M": "30",
                "%S": "52",
            }.get(fmt, "")
            mock_datetime_module.datetime.now.return_value = mock_now

            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            # Verify mkdir was called to create the date-based directory
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_output_with_stockpile_placeholders(
        self, sample_stockpile: Stockpile
    ) -> None:
        """Test file output with stockpile-related placeholders.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = FileOutputHandler(
            default_file_path="{timestamp}_{stockpile_type}_{stockpile_name}_{resolution}.json"
        )

        with (
            patch("pathlib.Path.open") as mock_open,
            patch("pathlib.Path.mkdir"),
            patch("foxhole_stockpiles.handlers.file.datetime") as mock_datetime_module,
        ):
            mock_now = Mock()
            mock_now.strftime.side_effect = lambda fmt: {
                "%Y-%m-%d_%H-%M-%S": "2025-01-24_14-30-52",
                "%Y": "2025",
                "%m": "01",
                "%d": "24",
                "%H": "14",
                "%M": "30",
                "%S": "52",
            }.get(fmt, "")
            mock_datetime_module.datetime.now.return_value = mock_now

            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_output_no_path(self, sample_stockpile: Stockpile) -> None:
        """Test file output raises error when no path provided.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        handler = FileOutputHandler()

        with pytest.raises(ValueError, match="File path must be provided"):
            await handler.handle([sample_stockpile])

    @pytest.mark.asyncio
    async def test_file_output_csv_format(self, sample_stockpile: Stockpile) -> None:
        """Test file output with CSV format.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        csv_settings = CsvFormatSettings(type=OutputFormat.CSV, include_header=True)
        handler = FileOutputHandler(default_file_path="output.csv", format_settings=csv_settings)

        with patch("pathlib.Path.open") as mock_open, patch("pathlib.Path.mkdir"):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            mock_file.write.assert_called_once()
            written_data = mock_file.write.call_args[0][0]

            # Verify CSV structure
            lines = written_data.split("\n")
            assert len(lines) == 4  # 1 header + 3 items
            # Header starts with stockpile_name
            assert lines[0] == (
                "Stockpile Name,Stockpile Type,Code,Crated,Quantity,Confidence,Shard,Ingame Time"
            )
            # Check first data row has stockpile_name
            assert lines[1].startswith("Test Stockpile,")
            assert "BasicMaterialsIcon" in lines[1]
            assert ",0," in lines[1]  # crated = 0 (false)
            assert "100" in lines[1]
            assert "0.95" in lines[1]  # confidence
            assert "Test Stockpile" in lines[1]
            assert "Seaport" in lines[1]

    @pytest.mark.asyncio
    async def test_file_output_tsv_format(self, sample_stockpile: Stockpile) -> None:
        """Test file output with TSV format.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        tsv_settings = CsvFormatSettings(type=OutputFormat.TSV, include_header=True)
        handler = FileOutputHandler(default_file_path="output.tsv", format_settings=tsv_settings)

        with patch("pathlib.Path.open") as mock_open, patch("pathlib.Path.mkdir"):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            mock_file.write.assert_called_once()
            written_data = mock_file.write.call_args[0][0]

            # Verify TSV structure (tab-separated)
            lines = written_data.split("\n")
            assert len(lines) == 4  # 1 header + 3 items
            assert "\t" in lines[0]  # Tab separator
            assert lines[0] == (
                "Stockpile Name\tStockpile Type\tCode\tCrated\tQuantity"
                "\tConfidence\tShard\tIngame Time"
            )

    @pytest.mark.asyncio
    async def test_file_output_csv_no_header(self, sample_stockpile: Stockpile) -> None:
        """Test file output with CSV format without header.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        csv_settings = CsvFormatSettings(type=OutputFormat.CSV, include_header=False)
        handler = FileOutputHandler(default_file_path="output.csv", format_settings=csv_settings)

        with patch("pathlib.Path.open") as mock_open, patch("pathlib.Path.mkdir"):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile])

            mock_file.write.assert_called_once()
            written_data = mock_file.write.call_args[0][0]

            # Verify no header - only data rows
            lines = written_data.split("\n")
            assert len(lines) == 3  # 3 items, no header
            assert lines[0].startswith("Test Stockpile,")  # stockpile_name first

    @pytest.mark.asyncio
    async def test_file_output_csv_multiple_stockpiles(self, sample_stockpile: Stockpile) -> None:
        """Test file output with CSV format and multiple stockpiles.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        second_stockpile = Stockpile(
            name="Second Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[StockpileItem(quantity=200, code="SulfurIcon", confidence=0.99)],
            shard="TEST",
            resolution="1920x1080",
        )

        csv_settings = CsvFormatSettings(type=OutputFormat.CSV, include_header=True)
        handler = FileOutputHandler(default_file_path="output.csv", format_settings=csv_settings)

        with patch("pathlib.Path.open") as mock_open, patch("pathlib.Path.mkdir"):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            await handler.handle([sample_stockpile, second_stockpile])

            mock_file.write.assert_called_once()
            written_data = mock_file.write.call_args[0][0]

            # Verify CSV structure with multiple stockpiles
            lines = written_data.split("\n")
            assert len(lines) == 5  # 1 header + 3 items from first + 1 item from second

            # First stockpile items have name "Test Stockpile"
            assert lines[1].startswith("Test Stockpile,")
            assert lines[2].startswith("Test Stockpile,")
            assert lines[3].startswith("Test Stockpile,")

            # Second stockpile item has name "Second Stockpile"
            assert lines[4].startswith("Second Stockpile,")
            assert "SulfurIcon" in lines[4]

    def test_fix_extension_replaces_wrong_extension(self) -> None:
        """Test that _fix_extension replaces wrong extensions."""
        # CSV format with .json extension should become .csv
        csv_settings = CsvFormatSettings(type=OutputFormat.CSV)
        handler = FileOutputHandler(format_settings=csv_settings)
        assert handler._fix_extension("output.json") == "output.csv"
        assert handler._fix_extension("folder/output.json") == "folder/output.csv"

        # TSV format with .csv extension should become .tsv
        tsv_settings = CsvFormatSettings(type=OutputFormat.TSV)
        handler = FileOutputHandler(format_settings=tsv_settings)
        assert handler._fix_extension("output.csv") == "output.tsv"

        # JSON format with .csv extension should become .json
        json_settings = JsonFormatSettings()
        handler = FileOutputHandler(format_settings=json_settings)
        assert handler._fix_extension("output.csv") == "output.json"

    def test_fix_extension_adds_missing_extension(self) -> None:
        """Test that _fix_extension adds extension when missing."""
        # No extension should add the correct one
        csv_settings = CsvFormatSettings(type=OutputFormat.CSV)
        handler = FileOutputHandler(format_settings=csv_settings)
        assert handler._fix_extension("output") == "output.csv"

        tsv_settings = CsvFormatSettings(type=OutputFormat.TSV)
        handler = FileOutputHandler(format_settings=tsv_settings)
        assert handler._fix_extension("output") == "output.tsv"

        json_settings = JsonFormatSettings()
        handler = FileOutputHandler(format_settings=json_settings)
        assert handler._fix_extension("output") == "output.json"

    def test_fix_extension_replaces_unknown_extension(self) -> None:
        """Test that _fix_extension replaces unknown extensions."""
        # Unknown extensions (not .json, .csv, .tsv) should also be replaced
        csv_settings = CsvFormatSettings(type=OutputFormat.CSV)
        handler = FileOutputHandler(format_settings=csv_settings)
        assert handler._fix_extension("output.txt") == "output.csv"
        assert handler._fix_extension("data.xml") == "data.csv"

        tsv_settings = CsvFormatSettings(type=OutputFormat.TSV)
        handler = FileOutputHandler(format_settings=tsv_settings)
        assert handler._fix_extension("output.txt") == "output.tsv"

        json_settings = JsonFormatSettings()
        handler = FileOutputHandler(format_settings=json_settings)
        assert handler._fix_extension("output.dat") == "output.json"


class TestWebhookOutputHandler:
    """Test cases for WebhookOutputHandler."""

    @pytest.mark.asyncio
    async def test_webhook_output_success(self, sample_stockpile: Stockpile) -> None:
        """Test successful webhook output.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        webhook_settings = WebhookHandlerSettings(url="https://example.com/webhook")
        webhook_response = {"status": "success", "id": "12345"}

        with patch("foxhole_stockpiles.handlers.webhook.WebhookConnector") as mock_connector_class:
            mock_connector = Mock()
            mock_connector.send_stockpile = AsyncMock(return_value=webhook_response)
            mock_connector_class.return_value = mock_connector

            handler = WebhookOutputHandler(webhook_settings=webhook_settings)
            result = await handler.handle([sample_stockpile])

            assert result == webhook_response
            mock_connector.send_stockpile.assert_called_once()
            # Verify payload structure
            call_args = mock_connector.send_stockpile.call_args
            payload = call_args.kwargs["payload"]
            assert "stockpiles" in payload
            assert len(payload["stockpiles"]) == 1

    @pytest.mark.asyncio
    async def test_webhook_output_with_token(self, sample_stockpile: Stockpile) -> None:
        """Test webhook output with custom token.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        webhook_settings = WebhookHandlerSettings(url="https://example.com/webhook")
        custom_token = "custom_token_123"
        webhook_response = {"status": "success", "id": "12345"}

        with patch("foxhole_stockpiles.handlers.webhook.WebhookConnector") as mock_connector_class:
            mock_connector = Mock()
            mock_connector.send_stockpile = AsyncMock(return_value=webhook_response)
            mock_connector_class.return_value = mock_connector

            handler = WebhookOutputHandler(webhook_settings=webhook_settings)
            result = await handler.handle([sample_stockpile], token=custom_token)

            assert result == webhook_response
            # Verify token was passed
            call_args = mock_connector.send_stockpile.call_args
            assert call_args.kwargs["token"] == custom_token

    @pytest.mark.asyncio
    async def test_webhook_output_no_url(self, sample_stockpile: Stockpile) -> None:
        """Test webhook output when URL is not configured.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        webhook_settings = WebhookHandlerSettings(url="")

        with patch("foxhole_stockpiles.handlers.webhook.WebhookConnector"):
            handler = WebhookOutputHandler(webhook_settings=webhook_settings)
            result = await handler.handle([sample_stockpile])

            assert result == ["URL not configured"]

    @pytest.mark.asyncio
    async def test_webhook_output_multiple_stockpiles(self, sample_stockpile: Stockpile) -> None:
        """Test webhook output with multiple stockpiles.

        Args:
            sample_stockpile (Stockpile): Sample stockpile data from fixture.
        """
        second_stockpile = Stockpile(
            name="Second Stockpile",
            type=StockpileType.STORAGE_DEPOT,
            items=[],
            resolution="1920x1080",
        )

        webhook_settings = WebhookHandlerSettings(url="https://example.com/webhook")
        webhook_response = {"status": "success", "count": 2}

        with patch("foxhole_stockpiles.handlers.webhook.WebhookConnector") as mock_connector_class:
            mock_connector = Mock()
            mock_connector.send_stockpile = AsyncMock(return_value=webhook_response)
            mock_connector_class.return_value = mock_connector

            handler = WebhookOutputHandler(webhook_settings=webhook_settings)
            result = await handler.handle([sample_stockpile, second_stockpile])

            assert result == webhook_response
            # Verify payload contains both stockpiles
            call_args = mock_connector.send_stockpile.call_args
            payload = call_args.kwargs["payload"]
            assert "stockpiles" in payload
            assert len(payload["stockpiles"]) == 2
