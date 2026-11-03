"""Fill the templates of the text around a stockpile image."""

import re
from typing import Final

from foxhole_stockpiles.models.stockpile import Stockpile

_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(\w+)\}")


def _build_values(stockpile: Stockpile) -> dict[str, str]:
    """Build the value of each placeholder.

    Args:
        stockpile (Stockpile): The stockpile.

    Returns:
        dict[str, str]: The text of each placeholder name.
    """
    return {
        "name": stockpile.name or "",
        "type": str(stockpile.type or ""),
        "hex": stockpile.hex or "",
        "shard": stockpile.shard or "",
        "ingame_timestamp": stockpile.ingame_timestamp or "",
        "timestamp": stockpile.timestamp.strftime("%Y-%m-%d %H:%M"),
        "resolution": stockpile.resolution or "",
        "item_count": str(len(stockpile.items)),
        # A negative quantity means unknown.
        "total_items": str(total_quantity(stockpile)),
    }


def total_quantity(stockpile: Stockpile) -> int:
    """Add up the quantities that are known.

    Args:
        stockpile (Stockpile): The stockpile.

    Returns:
        int: The total, without the items whose quantity is unknown.
    """
    return sum(item.quantity for item in stockpile.items if item.quantity >= 0)


def fill_template(template: str, stockpile: Stockpile) -> str:
    """Replace the placeholders of a template with the values of a stockpile.

    Not ``str.format``: a template must not reach attributes of the values, and a
    stray brace must not fail the send. Anything unknown stays as written.

    Args:
        template (str): The text, with placeholders such as ``{name}``.
        stockpile (Stockpile): The stockpile.

    Returns:
        str: The text with its values.
    """
    values = _build_values(stockpile)
    return _PLACEHOLDER.sub(lambda match: values.get(match[1], match[0]), template)
