"""Tests for handlers.sheets module."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from foxhole_stockpiles.core.settings.sections import SheetsHandlerSettings
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.handlers import sheets as sheets_mod
from foxhole_stockpiles.handlers.sheets import SheetsOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem

_VALID_URL = "https://docs.google.com/spreadsheets/d/12345/edit?gid=0#gid=0"
_ALL_PARAMS = (
    "timestamp,timestamp_datetime,structure_type,region,structure_x,structure_y,"
    "stockpile_name,item_code_name,item_display_name,item_quantity,item_crated,NONE"
)


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

    @pytest.mark.asyncio
    async def test_handle_no_start_cell(self, sample_stockpile: Stockpile) -> None:
        """A missing start cell returns a message."""
        settings = SheetsHandlerSettings(
            creds_path="mock", spreadsheet_url=_VALID_URL, sheet_id="Sheet1", start_cell=""
        )
        result = await SheetsOutputHandler(settings).handle([sample_stockpile])
        assert result == {"message": "Start cell missing"}

    @pytest.mark.asyncio
    async def test_handle_no_row_format(self, sample_stockpile: Stockpile) -> None:
        """A missing row format returns a message."""
        settings = SheetsHandlerSettings(
            creds_path="mock",
            spreadsheet_url=_VALID_URL,
            sheet_id="Sheet1",
            start_cell="A1",
            row_format=None,
        )
        result = await SheetsOutputHandler(settings).handle([sample_stockpile])
        assert result == {"message": "Row format missing"}

    @pytest.mark.asyncio
    async def test_handle_success(self, sample_stockpile: Stockpile) -> None:
        """A valid configuration appends rows and returns ok."""
        settings = SheetsHandlerSettings(
            creds_path="mock",
            spreadsheet_url=_VALID_URL,
            sheet_id="Sheet1",
            start_cell="A1",
            row_format="item_code_name,item_quantity",
        )
        with patch.object(sheets_mod, "build", return_value=MagicMock()) as build:
            result = await SheetsOutputHandler(settings).handle([sample_stockpile])
        build.assert_called_once()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_handle_http_error(self, sample_stockpile: Stockpile) -> None:
        """An API HttpError is surfaced as a failure message."""
        settings = SheetsHandlerSettings(
            creds_path="mock",
            spreadsheet_url=_VALID_URL,
            sheet_id="Sheet1",
            start_cell="A1",
            row_format="item_code_name",
        )
        resp = MagicMock()
        resp.status = 500
        resp.reason = "Server Error"
        error = HttpError(resp, b"{}")
        with patch.object(sheets_mod, "build", side_effect=error):
            result = await SheetsOutputHandler(settings).handle([sample_stockpile])
        assert result == {"message": "Appending failed"}


class TestStockpilesToRows:
    """Test suite for SheetsOutputHandler.stockpiles_to_rows."""

    def test_none_when_no_row_format(self) -> None:
        """An empty row format yields None."""
        handler = SheetsOutputHandler(SheetsHandlerSettings(creds_path="mock", row_format=None))
        assert handler.stockpiles_to_rows([]) is None

    def test_all_params_for_reserve(self) -> None:
        """Every supported row parameter maps to a cell value."""
        settings = SheetsHandlerSettings(creds_path="mock", row_format=_ALL_PARAMS)
        handler = SheetsOutputHandler(settings)
        stockpile = Stockpile(
            name="Reserve A",
            type=StockpileType.SEAPORT,
            hex="TerminusHex",
            coords=StockpileCoords(x=0.25, y=0.75),
            is_reserve=True,
            items=[StockpileItem(code="Rifle", quantity=7, crated=True)],
            timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        rows = handler.stockpiles_to_rows([stockpile])
        assert rows is not None
        row = rows[0]
        assert len(row) == 12
        assert row[2] == StockpileType.SEAPORT
        assert row[3] == "TerminusHex"
        assert row[4] == 0.25
        assert row[6] == "Reserve A"  # reserve uses its name
        assert row[7] == "Rifle"
        assert row[9] == 7
        assert row[10] is True
        assert row[11] is None

    def test_public_name_and_missing_coords(self) -> None:
        """A non-reserve uses 'Public' and missing coords default to 0."""
        settings = SheetsHandlerSettings(
            creds_path="mock", row_format="stockpile_name,structure_x,structure_y"
        )
        handler = SheetsOutputHandler(settings)
        stockpile = Stockpile(
            name="Ignored",
            type=StockpileType.SEAPORT,
            hex="H",
            coords=None,
            is_reserve=False,
            items=[StockpileItem(code="X", quantity=1, crated=False)],
        )
        rows = handler.stockpiles_to_rows([stockpile])
        assert rows == [["Public", 0, 0]]
