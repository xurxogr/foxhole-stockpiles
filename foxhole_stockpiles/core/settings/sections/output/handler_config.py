"""Output handler configuration."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

from foxhole_stockpiles.core.settings.sections.output.console_handler import (
    ConsoleHandlerSettings,
)
from foxhole_stockpiles.core.settings.sections.output.csv_format import CsvFormatSettings
from foxhole_stockpiles.core.settings.sections.output.file_handler import FileHandlerSettings
from foxhole_stockpiles.core.settings.sections.output.json_format import JsonFormatSettings
from foxhole_stockpiles.core.settings.sections.output.return_handler import ReturnHandlerSettings
from foxhole_stockpiles.core.settings.sections.output.sheets_handler import SheetsHandlerSettings
from foxhole_stockpiles.core.settings.sections.output.webhook_handler import (
    WebhookHandlerSettings,
)
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType


def _get_format_discriminator(v: dict[str, Any] | BaseModel) -> str:
    """Get discriminator value for format settings."""
    if isinstance(v, dict):
        return str(v.get("type", OutputFormat.JSON))
    return str(getattr(v, "type", OutputFormat.JSON))


def _get_handler_discriminator(v: dict[str, Any] | BaseModel) -> str:
    """Get discriminator value for handler settings."""
    if isinstance(v, dict):
        return str(v.get("type", OutputHandlerType.RETURN))
    return str(getattr(v, "type", OutputHandlerType.RETURN))


FormatSettings = Annotated[
    Annotated[JsonFormatSettings, Tag(OutputFormat.JSON)]
    | Annotated[CsvFormatSettings, Tag(OutputFormat.CSV)]
    | Annotated[CsvFormatSettings, Tag(OutputFormat.TSV)],
    Discriminator(_get_format_discriminator),
]

HandlerSettings = Annotated[
    Annotated[ReturnHandlerSettings, Tag(OutputHandlerType.RETURN)]
    | Annotated[FileHandlerSettings, Tag(OutputHandlerType.FILE)]
    | Annotated[WebhookHandlerSettings, Tag(OutputHandlerType.WEBHOOK)]
    | Annotated[ConsoleHandlerSettings, Tag(OutputHandlerType.CONSOLE)]
    | Annotated[SheetsHandlerSettings, Tag(OutputHandlerType.SHEETS)],
    Discriminator(_get_handler_discriminator),
]


class OutputHandlerConfig(BaseModel):
    """Configuration for a single output handler."""

    name: str = Field(description="Human-readable name for this output handler")
    format: FormatSettings = Field(
        description="Output format settings",
        default_factory=JsonFormatSettings,
    )
    handler: HandlerSettings = Field(
        description="Output handler settings",
        default_factory=ReturnHandlerSettings,
    )

    @model_validator(mode="after")
    def enforce_json_for_non_file_handlers(self) -> "OutputHandlerConfig":
        """Enforce JSON format for handlers that don't support CSV/TSV.

        Only file handlers support CSV/TSV formats. Webhook, return, and console
        handlers are forced to use JSON format.
        """
        handler_type = self.handler.type
        if isinstance(handler_type, str):
            handler_type = OutputHandlerType(handler_type)

        # Only file handler supports CSV/TSV
        if handler_type != OutputHandlerType.FILE:
            if not isinstance(self.format, JsonFormatSettings):
                self.format = JsonFormatSettings()

        return self

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Primary Webhook",
                "format": {"type": "json"},
                "handler": {
                    "type": "webhook",
                    "url": "https://api.example.com/stockpiles",
                    "auth_type": "bearer",
                    "token": "your-token",
                },
            }
        },
    )
