"""Enums for output handler types."""

from enum import StrEnum


class OutputHandlerType(StrEnum):
    """Supported output handler types."""

    RETURN = "return"
    FILE = "file"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    SHEETS = "google sheets"
