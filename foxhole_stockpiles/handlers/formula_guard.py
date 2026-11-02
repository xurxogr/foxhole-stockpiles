"""Protection against formula injection in spreadsheet output (CWE-1236)."""

from typing import Final

# Stockpile, region and item text comes from OCR, `.sav` and clipboard data, which
# other players or a crafted clipboard can control. Spreadsheets evaluate a cell
# starting with one of these, and skip leading whitespace before deciding.
_FORMULA_PREFIXES: Final[tuple[str, ...]] = ("=", "+", "-", "@")


def neutralize_formula(value: str) -> str:
    """Force a value a spreadsheet would evaluate to be read as plain text.

    Args:
        value (str): The value about to be written to a cell.

    Returns:
        str: The value prefixed with a single quote if it would start a formula,
            unchanged otherwise.
    """
    if value.lstrip().startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
