"""Enums for output destinations."""

from enum import StrEnum


class OutputDestination(StrEnum):
    """Supported output destinations for scanner results."""

    RETURN = "return"
    FILE = "file"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    SHEETS = "sheets"
