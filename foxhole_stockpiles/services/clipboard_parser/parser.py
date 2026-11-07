"""Top-level clipboard stockpile-export parsing entry point."""

from __future__ import annotations

import logging
from typing import Any

from foxhole_stockpiles.enums.hex import Hex
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.models.catalog_code import CatalogCode
from foxhole_stockpiles.models.clipboard_header import ClipboardHeader
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.clipboard_parser.code_map import ClipboardCodeMap
from foxhole_stockpiles.services.clipboard_parser.header import _parse_header
from foxhole_stockpiles.services.clipboard_parser.items import (
    _detect_locale,
    _infer_faction,
    _parse_item_line,
    _resolve_item_candidates,
    _select_code,
)

logger = logging.getLogger(__name__)


def parse_clipboard(text: str | None, code_map: ClipboardCodeMap) -> Stockpile | None:
    """Parse a clipboard stockpile export into a runtime ``Stockpile``.

    Args:
        text (str | None): Raw clipboard text.
        code_map (ClipboardCodeMap): Per-locale display-name -> code mapping.

    Returns:
        Stockpile | None: The parsed stockpile, or None if the text is not a
            recognized stockpile export.
    """
    if not text:
        return None

    lines = text.splitlines()
    header, body_start = _find_header(lines)
    if header is None:
        return None

    # Collect every item line first so the export language can be detected from the
    # names, and the whole file resolved in that language.
    raw_items = _parse_item_lines(lines[body_start:])
    locale = _detect_locale(code_map, [display for display, _ in raw_items])

    resolved = _resolve_items(code_map=code_map, raw_items=raw_items, locale=locale)
    faction = _vote_faction(resolved)
    items = [
        StockpileItem(code=_select_code(candidates, faction).code, quantity=qty, crated=crated)
        for candidates, crated, qty in resolved
    ]
    logger.info(
        "Parsed clipboard stockpile: %s (%d item(s), language: %s, inferred faction: %s)",
        header.type,
        len(items),
        locale or "unknown",
        faction,
    )

    return _build_stockpile(header=header, items=items, faction=faction)


def _find_header(lines: list[str]) -> tuple[ClipboardHeader | None, int]:
    """Parse the first line that is not blank as the header of the export.

    Args:
        lines (list[str]): The lines of the text.

    Returns:
        tuple[ClipboardHeader | None, int]: The header, if that line is one, and the
            position of the line after it.
    """
    for index, line in enumerate(lines):
        if line.strip():
            return _parse_header(line), index + 1
    return None, 0


def _parse_item_lines(lines: list[str]) -> list[tuple[str, int]]:
    """Parse the item lines of the export; blank lines only separate groups.

    Args:
        lines (list[str]): The lines after the header.

    Returns:
        list[tuple[str, int]]: The display name and quantity of each item line.
    """
    parsed = (_parse_item_line(line.strip()) for line in lines if line.strip())
    return [item for item in parsed if item is not None]


def _resolve_items(
    code_map: ClipboardCodeMap, raw_items: list[tuple[str, int]], locale: str | None
) -> list[tuple[list[CatalogCode], bool, int]]:
    """Resolve each item to its candidate codes, leaving out the unusable ones.

    Args:
        code_map (ClipboardCodeMap): Per-locale display-name -> code mapping.
        raw_items (list[tuple[str, int]]): The display name and quantity of each item.
        locale (str | None): The detected language of the export.

    Returns:
        list[tuple[list[CatalogCode], bool, int]]: The candidates, whether it is
            crated, and the quantity of each known item with a positive quantity.
    """
    resolved: list[tuple[list[CatalogCode], bool, int]] = []
    for display, quantity in raw_items:
        if quantity < 1:
            continue
        candidates, crated = _resolve_item_candidates(code_map, display, locale)
        if not candidates:
            logger.warning("Unknown item in clipboard export: %r", display)
            continue
        resolved.append((candidates, crated, quantity))
    return resolved


def _vote_faction(resolved: list[tuple[list[CatalogCode], bool, int]]) -> ItemFaction:
    """Infer the stockpile faction from the unambiguous items.

    An ambiguous item can't vote for the faction that disambiguates it.

    Args:
        resolved (list[tuple[list[CatalogCode], bool, int]]): The resolved items.

    Returns:
        ItemFaction: The inferred faction.
    """
    votes: dict[ItemFaction, int] = {ItemFaction.WARDENS: 0, ItemFaction.COLONIALS: 0}
    for candidates, _crated, _qty in resolved:
        if len(candidates) == 1 and candidates[0].faction in votes:
            votes[candidates[0].faction] += 1
    return _infer_faction(votes)


def _build_stockpile(
    header: ClipboardHeader, items: list[StockpileItem], faction: ItemFaction
) -> Stockpile:
    """Build the stockpile from the parts of the export.

    Args:
        header (ClipboardHeader): The header of the export.
        items (list[StockpileItem]): The final items.
        faction (ItemFaction): The inferred faction.

    Returns:
        Stockpile: The stockpile.
    """
    # Convert the localized region name from the export to its stable hex code;
    # an unrecognized region (e.g. one added before the enum is updated) keeps
    # its display name rather than collapsing to "Undefined".
    resolved_hex = Hex.from_display(header.hex)
    hex_name = header.hex if resolved_hex is Hex.UNDEFINED else resolved_hex.value

    # A NEUTRAL inference means it could not be determined, so the faction is left
    # unset rather than reported as neutral.
    inferred_faction = faction if faction in (ItemFaction.WARDENS, ItemFaction.COLONIALS) else None

    fields: dict[str, Any] = {
        "name": header.name,
        "type": header.type,
        "faction": inferred_faction,
        "hex": hex_name,
        "coords": header.coords,
        "town": header.town or None,
        "items": items,
    }
    if header.timestamp is not None:
        fields["timestamp"] = header.timestamp

    return Stockpile(**fields)
