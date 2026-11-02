"""Sheets output handler - appends data to Google Sheets spreadsheet."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Final

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from foxhole_stockpiles.connectors.credentials_unavailable_error import (
    CredentialsUnavailableError,
)
from foxhole_stockpiles.connectors.google_credentials import GoogleCredentialsProvider
from foxhole_stockpiles.core.settings.sections.output.sheets_handler import (
    SPREADSHEET_URL_PATTERN,
    SheetsHandlerSettings,
)
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.formula_guard import neutralize_formula
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.catalog_service import get_catalog_service

_SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/spreadsheets"]

CellValue = Callable[[Stockpile, StockpileItem], Any]

# What each column name of the configured row format writes.
_CELL_VALUES: Final[dict[str, CellValue]] = {
    "timestamp": lambda stockpile, _item: stockpile.timestamp.timestamp(),
    "timestamp_datetime": lambda stockpile, _item: str(stockpile.timestamp),
    "structure_type": lambda stockpile, _item: stockpile.type,
    "region": lambda stockpile, _item: stockpile.hex,
    "structure_x": lambda stockpile, _item: stockpile.coords.x if stockpile.coords else 0,
    "structure_y": lambda stockpile, _item: stockpile.coords.y if stockpile.coords else 0,
    "stockpile_name": lambda stockpile, _item: stockpile.name if stockpile.is_reserve else "Public",
    "item_code_name": lambda _stockpile, item: item.code,
    "item_display_name": lambda _stockpile, item: get_catalog_service().get_display_name(item.code),
    "item_quantity": lambda _stockpile, item: item.quantity,
    "item_crated": lambda _stockpile, item: item.crated,
    "NONE": lambda _stockpile, _item: None,
}


class SheetsOutputHandler(BaseOutputDestinationHandler):
    """Handles appending stockpile data to a Google Sheets spreadsheet."""

    def __init__(self, sheets_settings: SheetsHandlerSettings) -> None:
        """Initialize sheets output handler.

        Args:
            sheets_settings (SheetsHandlerSettings): Sheets configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self._credentials = GoogleCredentialsProvider(
            creds_path=sheets_settings.creds_path, scopes=_SCOPES
        )
        self._spreadsheet_url = sheets_settings.spreadsheet_url
        self._sheet_id = sheets_settings.sheet_id
        self._start_cell = sheets_settings.start_cell
        self._row_format = sheets_settings.row_format

    def _config_problem(self) -> str | None:
        """Find what makes the configuration unusable.

        Returns:
            str | None: A message for the user, or None if it is complete.
        """
        if self._spreadsheet_url is None:
            return "Spreadsheet URL missing"
        if SPREADSHEET_URL_PATTERN.search(self._spreadsheet_url) is None:
            return "Spreadsheet URL invalid"
        if self._sheet_id is None or not self._sheet_id.strip():
            return "Sheet ID missing"
        if self._start_cell is None or not self._start_cell.strip():
            return "Start cell missing"
        if self._row_format is None or not self._row_format.strip():
            return "Row format missing"
        return None

    def _append_rows(self, creds: Credentials, rows: list[Any] | None) -> None:
        """Append rows through the Sheets API. Blocks on the network.

        Args:
            creds (Credentials): Valid Google credentials.
            rows (list[Any] | None): The rows to append.
        """
        match = SPREADSHEET_URL_PATTERN.search(self._spreadsheet_url or "")
        spreadsheet_id = match.group(1) if match else ""
        # A1 notation doubles an apostrophe inside a quoted sheet name.
        sheet = (self._sheet_id or "").replace("'", "''")
        self.logger.debug("Appending to spreadsheet (Sheet: %s)", self._sheet_id)

        service = build("sheets", "v4", credentials=creds)
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet}'!{self._start_cell}",
                valueInputOption="USER_ENTERED",
                body={"values": rows},
            )
            .execute()
        )
        self.logger.debug("Append result: %s", result)

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> dict[str, Any]:
        """Append stockpile data to sheets spreadsheet in FIR format.

        The configuration is checked first, so a broken one is reported without
        opening a browser window to authorize.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to send
            **kwargs: Additional parameters:
                - None

        Returns:
            dict[str, Any]: Append response data
        """
        problem = self._config_problem()
        if problem is not None:
            return {"message": problem}

        try:
            creds = await asyncio.to_thread(self._credentials.load)
        except CredentialsUnavailableError as e:
            return {"message": str(e)}

        rows = self.stockpiles_to_rows(stockpiles)
        try:
            await asyncio.to_thread(self._append_rows, creds=creds, rows=rows)
        except HttpError:
            return {"message": "Appending failed"}
        return {"status": "ok"}

    def stockpiles_to_rows(self, stockpiles: list[Stockpile]) -> list[Any] | None:
        """Transform stockpile data into cell format, for usage in CSV and spreadsheet export.

        Rows are written with USER_ENTERED, so Sheets evaluates formulas. Every text
        cell passes through here, whatever column it belongs to.

        Args:
            stockpiles (list[Stockpile]): Stockpile data

        Returns:
            list[Any] | None: Stockpiles in cell format, or None without a row format.
        """
        if self._row_format is None or not self._row_format.strip():
            return None

        columns = [
            _CELL_VALUES[name] for name in self._row_format.split(",") if name in _CELL_VALUES
        ]
        return [
            [self._safe_cell(column(stockpile, item)) for column in columns]
            for stockpile in stockpiles
            for item in stockpile.items
        ]

    @staticmethod
    def _safe_cell(value: Any) -> Any:
        """Neutralize a cell value if it is text.

        Args:
            value (Any): The cell value.

        Returns:
            Any: The value, safe to write with USER_ENTERED.
        """
        return neutralize_formula(value) if isinstance(value, str) else value
