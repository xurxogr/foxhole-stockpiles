"""Fill the path templates of the handlers that write files."""

import datetime
from pathlib import Path

from foxhole_stockpiles.core.safe_path_segment import safe_path_segment
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_image.placeholders import hex_name, total_quantity


def stockpile_type_label(stockpile: Stockpile | None) -> str:
    """Get the type of a stockpile as text for a path or a row.

    Args:
        stockpile (Stockpile | None): The stockpile to get the type from.

    Returns:
        str: The type, or "Unknown".
    """
    if not stockpile or not stockpile.type:
        return "Unknown"
    if isinstance(stockpile.type, str):
        return stockpile.type.title()
    return stockpile.type.value.title()


def _build_placeholders(stockpiles: list[Stockpile]) -> dict[str, str]:
    """Build the values a path template can use.

    What depends on a stockpile is taken from the first one.

    Args:
        stockpiles (list[Stockpile]): The stockpiles being written, at least one.

    Returns:
        dict[str, str]: The value of each placeholder, not yet safe for a path.
    """
    first = stockpiles[0]
    now = datetime.datetime.now()
    name = (first.name or "Unknown") if len(stockpiles) == 1 else "multiple_stockpiles"
    stockpile_type = stockpile_type_label(first)
    return {
        "{timestamp}": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "{year}": now.strftime("%Y"),
        "{month}": now.strftime("%m"),
        "{day}": now.strftime("%d"),
        "{hour}": now.strftime("%H"),
        "{minute}": now.strftime("%M"),
        "{second}": now.strftime("%S"),
        "{stockpile_type}": stockpile_type,
        "{stockpile_name}": name,
        # The names of the text of images and messages, so one template works in
        # every field.
        "{type}": stockpile_type,
        "{name}": name,
        "{resolution}": first.resolution or "Unknown",
        "{hex}": hex_name(first.hex) or "Unknown",
        "{coords}": first.coords.to_key().replace("_", "-") if first.coords else "0-0",
        "{ingame_timestamp}": first.ingame_timestamp or "Unknown",
        "{item_count}": str(sum(len(stockpile.items) for stockpile in stockpiles)),
        "{total_items}": str(sum(total_quantity(stockpile) for stockpile in stockpiles)),
    }


def fill_path_template(template: str, stockpiles: list[Stockpile]) -> str:
    """Replace the placeholders of a path with values that are safe in a path.

    Fix the extension first: a dot in a substituted value is not an extension.

    Args:
        template (str): The path, with its placeholders.
        stockpiles (list[Stockpile]): The stockpiles being written, at least one.

    Returns:
        str: The path to write to.
    """
    filled = template
    for placeholder, value in _build_placeholders(stockpiles).items():
        filled = filled.replace(placeholder, safe_path_segment(value))
    return filled


def with_extension(path: str, extension: str) -> str:
    """Give a path the extension of what is written to it.

    Args:
        path (str): The path, which may already have another extension.
        extension (str): The extension, with its leading dot.

    Returns:
        str: The path with that extension.
    """
    current = Path(path)
    return str(current.with_suffix(extension)) if current.suffix else path + extension
