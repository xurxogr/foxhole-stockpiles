"""Refinery order queue access level enum."""

from enum import StrEnum


class RefineryAccessLevel(StrEnum):
    """Owner scope of a refinery order queue or storage.

    PERSONAL: owned by a single player.
    PUBLIC: shared with everyone.
    SQUAD: shared with a squad (identified by its squad id).
    """

    PERSONAL = "personal"
    PUBLIC = "public"
    SQUAD = "squad"

    @classmethod
    def from_string(cls, value: str) -> "RefineryAccessLevel":
        """Convert a string to a RefineryAccessLevel.

        Accepts the plain value or the in-game enum name
        (``ERefineryOrderAccessLevel::Squad``), case-insensitive.

        Args:
            value (str): The string to convert.

        Returns:
            RefineryAccessLevel: The corresponding access level.

        Raises:
            ValueError: If the value is not a valid access level.
        """
        normalized = value.strip().lower().removeprefix("erefineryorderaccesslevel::")
        try:
            return cls(normalized)
        except ValueError:
            raise ValueError(f"Invalid refinery access level: {value!r}") from None
