"""Pure activity-feed line formatting shared by the capture panel's controls."""

from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.stockpile import Stockpile


def ocr_summary(stockpile: Stockpile) -> str:
    """Build a one-line OCR result summary: ``type | name | N items``.

    Args:
        stockpile (Stockpile): The scanned stockpile.

    Returns:
        str: The summary line, omitting the name when absent.
    """
    parts: list[str] = [str(stockpile.type)]
    if stockpile.name:
        parts.append(stockpile.name)
    parts.append(t("activity.item_count", count=len(stockpile.items)))
    return " | ".join(parts)


def stockpile_summary(stockpile: Stockpile) -> str:
    """Build a one-line summary: ``type | name | hex | x, y | N items``.

    Args:
        stockpile (Stockpile): The stockpile to summarize.

    Returns:
        str: The summary line, dropping any field that is absent.
    """
    parts: list[str] = [str(stockpile.type)]
    if stockpile.name:
        parts.append(stockpile.name)
    if stockpile.hex:
        parts.append(stockpile.hex)
    if stockpile.coords is not None:
        parts.append(f"{stockpile.coords.x:.2f}, {stockpile.coords.y:.2f}")
    parts.append(t("activity.item_count", count=len(stockpile.items)))
    return " | ".join(parts)
