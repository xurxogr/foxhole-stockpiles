"""Validation of the mod name recorded against imported icon templates."""

import re

# Letters, digits, spaces, underscores and hyphens only: no path separators,
# dots or shell metacharacters.
_MOD_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_ -]+$")
_MAX_MOD_NAME_LENGTH = 100


def validate_mod_name(mod_name: str) -> str:
    """Validate and normalize a mod name.

    Args:
        mod_name (str): The mod name entered by the user.

    Returns:
        str: The name with surrounding whitespace removed.

    Raises:
        ValueError: If the name is empty, too long or has unsafe characters.
    """
    normalized = mod_name.strip()

    if not normalized:
        raise ValueError("Mod name cannot be empty")

    if len(normalized) > _MAX_MOD_NAME_LENGTH:
        raise ValueError(f"Mod name is too long (max {_MAX_MOD_NAME_LENGTH} characters)")

    if not _MOD_NAME_PATTERN.match(normalized):
        raise ValueError(
            "Mod name can only contain alphanumeric characters, spaces, underscores, and hyphens"
        )

    return normalized
