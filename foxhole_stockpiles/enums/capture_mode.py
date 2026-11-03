"""Interaction mode of the capture controls."""

from enum import StrEnum


class CaptureMode(StrEnum):
    """How a capture control of the main window (clipboard, .sav file) behaves.

    MANUAL: a hotkey reads the source once on each press.
    MONITOR: the source is polled automatically and what is new is emitted.
    """

    MANUAL = "manual"
    MONITOR = "monitor"

    @classmethod
    def from_string(cls, value: str | None = None) -> "CaptureMode":
        """Convert a string to a CaptureMode, never returns None.

        Args:
            value (str | None): The string to convert (case-insensitive). Can be None.

        Returns:
            CaptureMode: The corresponding mode, defaults to MANUAL for invalid/empty input.
        """
        if not value:
            return cls.MANUAL

        normalized = value.strip().lower()
        if normalized == cls.MONITOR.value:
            return cls.MONITOR
        return cls.MANUAL
