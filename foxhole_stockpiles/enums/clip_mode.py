"""Clipboard processing interaction mode."""

from enum import StrEnum


class ClipMode(StrEnum):
    """How the main window's clipboard control behaves.

    MANUAL: a hotkey reads the clipboard once on each press.
    MONITOR: the clipboard is polled automatically and new exports are emitted.
    """

    MANUAL = "manual"
    MONITOR = "monitor"

    @classmethod
    def from_string(cls, value: str | None = None) -> "ClipMode":
        """Convert a string to a ClipMode, never returns None.

        Args:
            value (str | None): The string to convert (case-insensitive). Can be None.

        Returns:
            ClipMode: The corresponding mode, defaults to MANUAL for invalid/empty input.
        """
        if not value:
            return cls.MANUAL

        normalized = value.strip().lower()
        if normalized == cls.MONITOR.value:
            return cls.MONITOR
        return cls.MANUAL
