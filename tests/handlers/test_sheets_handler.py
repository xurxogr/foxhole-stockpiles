"""Tests for handlers.sheets module."""

from datetime import UTC, datetime

import pytest

from foxhole_stockpiles.core.settings.sections import SheetsHandlerSettings
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.handlers.sheets import SheetsOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem


@pytest.fixture
def sheets_settings() -> SheetsHandlerSettings:
    """Create sheets settings for testing."""
    return SheetsHandlerSettings(
        creds_path="mock",
        spreadsheet_url="https://docs.google.com/spreadsheets/d/12345/edit?gid=0#gid=0",
        sheet_id="Sheet1",
    )


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


class TestSheetsOutputHandlerInit:
    """Test suite for SheetsOutputHandler initialization."""

    def test_init_with_settings(self, sheets_settings: SheetsHandlerSettings) -> None:
        """Test initialization with settings."""
        handler = SheetsOutputHandler(sheets_settings)
        assert handler._creds_path == "mock"
        assert (
            handler._spreadsheet_url
            == "https://docs.google.com/spreadsheets/d/12345/edit?gid=0#gid=0"
        )
        assert handler._sheet_id == "Sheet1"


class TestSheetsOutputHandlerHandle:
    """Test suite for SheetsOutputHandler.handle method."""

    @pytest.mark.asyncio
    async def test_handle_no_creds(self, sample_stockpile: Stockpile) -> None:
        """Test handling with no URL configured returns message."""
        settings = SheetsHandlerSettings(spreadsheet_url=None)

        handler = SheetsOutputHandler(settings)

        result = await handler.handle([sample_stockpile])

        assert result == {"message": "Credentials missing"}

    @pytest.mark.asyncio
    async def test_handle_no_url(self, sample_stockpile: Stockpile) -> None:
        """Test handling with no URL configured returns message."""
        settings = SheetsHandlerSettings(spreadsheet_url=None, creds_path="mock")
        handler = SheetsOutputHandler(settings)

        result = await handler.handle([sample_stockpile])

        assert result == {"message": "Spreadsheet URL missing"}

    @pytest.mark.asyncio
    async def test_handle_bad_url(self, sample_stockpile: Stockpile) -> None:
        """Test handling with no URL configured returns message."""
        settings = SheetsHandlerSettings(spreadsheet_url="abcd", creds_path="mock")
        handler = SheetsOutputHandler(settings)

        result = await handler.handle([sample_stockpile])

        assert result == {"message": "Spreadsheet URL invalid"}

    @pytest.mark.asyncio
    async def test_handle_no_sheet(self, sample_stockpile: Stockpile) -> None:
        """Test handling with no URL configured returns message."""
        settings = SheetsHandlerSettings(
            spreadsheet_url="https://docs.google.com/spreadsheets/d/1234/edit?gid=0#gid=0",
            sheet_id="",
            creds_path="mock",
        )
        handler = SheetsOutputHandler(settings)

        result = await handler.handle([sample_stockpile])

        assert result == {"message": "Sheet ID missing"}
