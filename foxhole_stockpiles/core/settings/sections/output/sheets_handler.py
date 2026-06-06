"""Sheets handler settings."""

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType


class SheetsHandlerSettings(BaseModel):
    """Settings for sheets output handler."""

    type: OutputHandlerType = Field(default=OutputHandlerType.SHEETS, description="Handler type")
    creds_path: str | None = Field(
        description="Path to the Google OAuth Credentials JSON file", default=None
    )

    spreadsheet_url: str | None = Field(description="Spreadsheet to append data to", default=None)
    sheet_id: str | None = Field(description="Target sheet id for appending data", default=None)
    start_cell: str | None = Field(description="Top-Left cell of append area", default=None)
    row_format: str | None = Field(description="Row formatting", default=None)

    model_config = ConfigDict(extra="forbid")
