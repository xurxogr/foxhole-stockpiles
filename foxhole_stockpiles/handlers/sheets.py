"""Sheets output handler - appends data to Google Sheets spreadsheet."""

import asyncio
import logging
import os
from pathlib import Path
from re import Match, search
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from foxhole_stockpiles.core.settings.sections.output.sheets_handler import SheetsHandlerSettings
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.models.stockpile import Stockpile


class SheetsOutputHandler(BaseOutputDestinationHandler):
    """Handles sending stockpile data to webhook endpoints."""

    def __init__(self, sheets_settings: SheetsHandlerSettings) -> None:
        """Initialize sheets output handler.

        Args:
            sheets_settings(SheetsHandlerSettings): Sheets configuration settings
        """
        self.logger = logging.getLogger(__name__)
        self._creds_path = sheets_settings.creds_path
        self._spreadsheet_url = sheets_settings.spreadsheet_url
        self._sheet_id = sheets_settings.sheet_id
        self._start_cell = sheets_settings.start_cell
        self._row_format = sheets_settings.row_format

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> dict[str, Any]:
        """Append stockpile data to sheets spreadsheet in FIR format.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to send
            **kwargs: Additional parameters:
                - None

        Returns:
            dict[str, Any]: Append response data
        """
        auth_scopes = ["https://www.googleapis.com/auth/spreadsheets"]  # Needed scopes to append

        creds = None
        if self._creds_path != "mock":  # crude fix for tests, needs revisiting
            # Try to find saved token, if it doesn't exist or is invalid, prompt reauth
            if os.path.exists(Path("~/.fs_token").expanduser()):
                # ignoring mypy error since it's a import issue
                creds = Credentials.from_authorized_user_file(  # type: ignore [no-untyped-call]
                    str(Path("~/.fs_token").expanduser()), auth_scopes
                )
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    await asyncio.to_thread(creds.refresh, Request())
                else:
                    if self._creds_path is None or not os.path.exists(self._creds_path):
                        return {"message": "Credentials missing"}
                    flow = InstalledAppFlow.from_client_secrets_file(self._creds_path, auth_scopes)
                    creds = await asyncio.to_thread(flow.run_local_server, port=0)
                # Save the credentials for the next run
                with open(Path("~/.fs_token").expanduser(), "w") as token:
                    if creds:
                        token.write(creds.to_json())

        if creds is None and self._creds_path != "mock":
            return {"message": "Credentials invalid or authorization failed"}

        if self._spreadsheet_url is None:
            return {"message": "Spreadsheet URL missing"}

        spreadsheet_id_match: Match[str] | None = search(
            pattern=r"(?<=https://docs.google.com/spreadsheets/d/).*(?=/)",
            string=self._spreadsheet_url,
        )  # Get spreadsheet ID from URL

        if spreadsheet_id_match is None:
            return {"message": "Spreadsheet URL invalid"}

        spreadsheet_id = spreadsheet_id_match.group()

        if self._sheet_id is None or self._sheet_id.strip() == "":
            return {"message": "Sheet ID missing"}

        if self._start_cell is None or self._start_cell.strip() == "":
            return {"message": "Start cell missing"}

        if self._row_format is None or self._row_format.strip() == "":
            return {"message": "Row format missing"}

        self.logger.debug(
            "Appending to spreadsheet (Spreadsheet ID: %s, Sheet: %s)",
            spreadsheet_id,
            self._sheet_id,
        )

        rows = self.stockpiles_to_rows(stockpiles)

        try:
            service = build("sheets", "v4", credentials=creds)

            # Call the Sheets API
            body = {"values": rows}
            result = await asyncio.to_thread(
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{self._sheet_id}'!{self._start_cell}",
                    valueInputOption="USER_ENTERED",
                    body=body,
                )
                .execute
            )

            self.logger.debug("Append result: %s", result)
            return {"status": "ok"}
        except HttpError:
            return {"message": "Appending failed"}

    def stockpiles_to_rows(self, stockpiles: list[Stockpile]) -> list[Any] | None:
        """Transform stockpile data into cell format, for usage in CSV and spreadsheet export.

        Args:
            stockpiles (list[Stockpile]): Stockpile data
        Returns:
            list[Any]: Stockpiles in cell format
            None: On failure
        """
        from foxhole_stockpiles.api.dependencies import get_catalog_service

        if self._row_format is None or self._row_format.strip() == "":
            return None

        row_params = self._row_format.split(",")

        values = []

        for stockpile in stockpiles:
            for item in stockpile.items:
                row: list[Any] = []

                for row_param in row_params:
                    match row_param:
                        case "timestamp":
                            row.append(stockpile.timestamp.timestamp())
                        case "timestamp_datetime":
                            row.append(str(stockpile.timestamp))
                        case "structure_type":
                            row.append(stockpile.type)
                        case "region":
                            row.append(stockpile.hex)
                        case "structure_x":
                            if stockpile.coords is None:
                                row.append(0)
                            else:
                                row.append(stockpile.coords.x)
                        case "structure_y":
                            if stockpile.coords is None:
                                row.append(0)
                            else:
                                row.append(stockpile.coords.y)
                        case "stockpile_name":
                            row.append(stockpile.name if stockpile.is_reserve else "Public")
                        case "item_code_name":
                            row.append(item.code)
                        case "item_display_name":
                            row.append(get_catalog_service().get_display_name(item.code))
                        case "item_quantity":
                            row.append(item.quantity)
                        case "item_crated":
                            row.append(item.crated)
                        case "NONE":
                            row.append(None)

                values.append(row)

        return values
