"""Protection against formula injection in spreadsheet output (CWE-1236)."""

import re
from typing import Final

# Stockpile, region and item text comes from OCR, `.sav` and clipboard data, which
# other players or a crafted clipboard can control. Spreadsheets evaluate a cell
# starting with one of these, and skip leading whitespace before deciding. Invisible
# characters and the fullwidth signs are covered too: they look the same to whoever
# reads the text, and a cell costs nothing to keep as plain text.
_FORMULA_START: Final[re.Pattern[str]] = re.compile(r"[\s﻿​-‍⁠]*[=+\-@＝＋－＠]")


def neutralize_formula(value: str) -> str:
    """Force a value a spreadsheet would evaluate to be read as plain text.

    Args:
        value (str): The value about to be written to a cell.

    Returns:
        str: The value prefixed with a single quote if it would start a formula,
            unchanged otherwise.
    """
    if _FORMULA_START.match(value):
        return "'" + value
    return value
