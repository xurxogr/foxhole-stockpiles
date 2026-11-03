"""File output handler - writes data to filesystem."""

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from foxhole_stockpiles.core.settings.sections.output.csv_format import (
    CSV_FIELDS,
    CSV_HEADERS,
    CsvFormatSettings,
)
from foxhole_stockpiles.core.settings.sections.output.json_format import JsonFormatSettings
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.formula_guard import neutralize_formula
from foxhole_stockpiles.handlers.path_template import (
    fill_path_template,
    stockpile_type_label,
    with_extension,
)
from foxhole_stockpiles.handlers.stockpile_json import stockpiles_to_json_payload
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem

FormatSettings = JsonFormatSettings | CsvFormatSettings


class FileOutputHandler(BaseOutputDestinationHandler):
    """Handles writing stockpile data to files."""

    def __init__(
        self,
        default_file_path: str | None = None,
        format_settings: FormatSettings | None = None,
    ) -> None:
        """Initialize file output handler.

        Args:
            default_file_path (str | None): Default file path if not provided in handle()
            format_settings (FormatSettings | None): Format settings for output
        """
        self.logger = logging.getLogger(__name__)
        self.default_file_path = default_file_path
        self.format_settings = format_settings or JsonFormatSettings()

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> None:
        """Write stockpile data to file.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to write
            **kwargs: Additional parameters:
                - file_path (str | Path): Path where to write the file

        Raises:
            ValueError: If no file path is provided
        """
        file_path_arg = kwargs.get("file_path")

        if not file_path_arg and not self.default_file_path:
            raise ValueError("File path must be provided via file_path argument or default")

        if len(stockpiles) == 0:
            self.logger.warning("No stockpiles to write, skipping file output")
            return

        file = str(file_path_arg) if file_path_arg else self.default_file_path or "output.json"

        # Fix the extension first: a dot in a substituted value is not an extension.
        file = self._fix_extension(file)
        output_path = Path(fill_path_template(template=file, stockpiles=stockpiles))
        content = self._format_output(stockpiles)

        def write_file() -> None:
            """Write stockpile data to file synchronously."""
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(write_file)

        self.logger.debug("Output saved to: %s", output_path)

    def _format_output(self, stockpiles: list[Stockpile]) -> str:
        """Format stockpile data based on format settings.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to format

        Returns:
            str: Formatted output string
        """
        if isinstance(self.format_settings, CsvFormatSettings):
            return self._format_csv(stockpiles)
        return self._format_json(stockpiles)

    def _format_json(self, stockpiles: list[Stockpile]) -> str:
        """Format stockpiles as JSON with wrapper object.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to format

        Returns:
            str: JSON formatted string with {"stockpiles": [...]} structure
        """
        payload = stockpiles_to_json_payload(stockpiles)
        return json.dumps(obj=payload, indent=2)

    def _format_csv(self, stockpiles: list[Stockpile]) -> str:
        """Format stockpile data as CSV/TSV.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to format

        Returns:
            str: CSV/TSV formatted string
        """
        separator = "\t" if self.format_settings.type == OutputFormat.TSV else ","
        lines: list[str] = []

        # Add header if enabled
        if (
            isinstance(self.format_settings, CsvFormatSettings)
            and self.format_settings.include_header
        ):
            lines.append(separator.join(CSV_HEADERS))

        # Add rows for each stockpile
        for stockpile in stockpiles:
            stockpile_lines = self._format_stockpile_csv_rows(
                stockpile=stockpile, separator=separator
            )
            lines.extend(stockpile_lines)

        return "\n".join(lines)

    def _format_stockpile_csv_rows(self, stockpile: Stockpile, separator: str) -> list[str]:
        """Format a single stockpile's items as CSV/TSV rows.

        Args:
            stockpile (Stockpile): The stockpile to format
            separator (str): Field separator (comma or tab)

        Returns:
            list[str]: List of CSV/TSV row strings
        """
        # Get stockpile-level values
        stockpile_name = stockpile.name or ""
        stockpile_type = stockpile_type_label(stockpile) if stockpile.type else ""
        shard = stockpile.shard or ""
        ingame_timestamp = stockpile.ingame_timestamp or ""

        def escape(value: str) -> str:
            return self._escape_csv_value(value=value, separator=separator)

        field_values: dict[str, Callable[[StockpileItem], str]] = {
            "stockpile_name": lambda _item: escape(stockpile_name),
            "stockpile_type": lambda _item: escape(stockpile_type),
            "code": lambda item: escape(item.code),
            "crated": lambda item: "1" if item.crated else "0",
            "quantity": lambda item: str(item.quantity),
            "confidence": lambda item: (
                str(round(item.confidence, 3)) if item.confidence is not None else ""
            ),
            "shard": lambda _item: escape(shard),
            "ingame_timestamp": lambda _item: escape(ingame_timestamp),
        }

        # Add a row for each item
        lines: list[str] = []
        for item in stockpile.items:
            row_values = [field_values[field](item) for field in CSV_FIELDS]
            lines.append(separator.join(row_values))

        return lines

    def _escape_csv_value(self, value: str, separator: str) -> str:
        """Escape a value for CSV/TSV output.

        Args:
            value (str): The value to escape
            separator (str): The field separator

        Returns:
            str: Escaped value
        """
        value = neutralize_formula(value)

        # Quote if value contains separator, quotes, or line breaks
        if separator in value or '"' in value or "\n" in value or "\r" in value:
            return '"' + value.replace('"', '""') + '"'
        return value

    def _fix_extension(self, file_path: str) -> str:
        """Fix the file extension based on format settings.

        Args:
            file_path (str): The file path to fix

        Returns:
            str: File path with correct extension
        """
        # Determine the correct extension based on format
        if self.format_settings.type == OutputFormat.TSV:
            correct_ext = ".tsv"
        elif self.format_settings.type == OutputFormat.CSV:
            correct_ext = ".csv"
        else:
            correct_ext = ".json"

        return with_extension(path=file_path, extension=correct_ext)
