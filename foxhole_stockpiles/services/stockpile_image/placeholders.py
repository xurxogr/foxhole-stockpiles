"""Fill the templates of the text around a stockpile image."""

import re
from typing import Final

from foxhole_stockpiles.enums.hex import Hex
from foxhole_stockpiles.models.stockpile import Stockpile

_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(\w+)\}")


def hex_name(hex_code: str | None) -> str:
    """Get the name of a hex as players know it.

    Args:
        hex_code (str | None): The code of the game, such as ``HeartlandsHex``.

    Returns:
        str: Its name, such as ``Heartlands``, the code itself if it is not known,
            or empty if there is none.
    """
    if not hex_code:
        return ""
    try:
        return Hex(hex_code).display_name
    except ValueError:
        return hex_code


def _build_values(stockpile: Stockpile, type_label: str) -> dict[str, str]:
    """Build the value of each placeholder.

    Args:
        stockpile (Stockpile): The stockpile.
        type_label (str): The name of its type.

    Returns:
        dict[str, str]: The text of each placeholder name.
    """
    return {
        "name": stockpile.name or "",
        "type": type_label,
        "hex": hex_name(stockpile.hex),
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


def fill_template(template: str, stockpile: Stockpile, type_label: str = "") -> str:
    """Replace the placeholders of a template with the values of a stockpile.

    Not ``str.format``: a template must not reach attributes of the values, and a
    stray brace must not fail the send. Anything unknown stays as written.

    Args:
        template (str): The text, with placeholders such as ``{name}``.
        stockpile (Stockpile): The stockpile.
        type_label (str): The name of its type, which depends on the language.

    Returns:
        str: The text with its values.
    """
    values = _build_values(stockpile=stockpile, type_label=type_label)
    return _PLACEHOLDER.sub(lambda match: values.get(match[1], match[0]), template)
