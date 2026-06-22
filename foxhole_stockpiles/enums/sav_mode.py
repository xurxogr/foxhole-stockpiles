"""SAV processing interaction mode."""

from enum import StrEnum


class SavMode(StrEnum):
    """How the main window's SAV control behaves.

    MANUAL: a hotkey scans the .sav file once on each press.
    MONITOR: the .sav file is polled automatically and changes are emitted.
    """

    MANUAL = "manual"
    MONITOR = "monitor"

    @classmethod
    def from_string(cls, value: str | None = None) -> "SavMode":
        """Convert a string to a SavMode, never returns None.

        Args:
            value (str | None): The string to convert (case-insensitive). Can be None.

        Returns:
            SavMode: The corresponding mode, defaults to MANUAL for invalid/empty input.
        """
        if not value:
            return cls.MANUAL

        normalized = value.strip().lower()
        if normalized == cls.MONITOR.value:
            return cls.MONITOR
        return cls.MANUAL
