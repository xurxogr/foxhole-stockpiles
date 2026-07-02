"""Top-level clipboard stockpile-export parsing entry point."""

from __future__ import annotations

import logging
from typing import Any

from foxhole_stockpiles.enums.hex import Hex
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.clipboard_parser.code_map import CatalogCode, ClipboardCodeMap
from foxhole_stockpiles.services.clipboard_parser.header import _Header, _parse_header
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
        code_map (ClipboardCodeMap): Per-locale display-name -> code lookup.

    Returns:
        Stockpile | None: The parsed stockpile, or None if the text is not a
            recognized stockpile export.
    """
    if not text:
        return None

    lines = text.splitlines()
    header: _Header | None = None
    body_start = 0
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        header = _parse_header(line)
        body_start = index + 1
        break

    if header is None:
        return None

    # Collect every item line first (blank lines are group separators), then
    # detect the export language from the names so the whole file reads in it.
    raw_items: list[tuple[str, int]] = []
    for line in lines[body_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        parsed = _parse_item_line(stripped)
        if parsed is not None:
            raw_items.append(parsed)

    locale = _detect_locale(code_map, [display for display, _ in raw_items])

    # Pass 1: resolve each kept item to its candidate code(s).
    resolved: list[tuple[list[CatalogCode], bool, int]] = []
    for display, quantity in raw_items:
        if quantity < 1:
            continue
        candidates, crated = _resolve_item_candidates(code_map, display, locale)
        if not candidates:
            logger.warning("Unknown item in clipboard export: %r", display)
            continue
        resolved.append((candidates, crated, quantity))

    # Infer the stockpile faction from the unambiguous items only (an ambiguous
    # item can't vote for the faction that disambiguates it).
    faction_votes: dict[ItemFaction, int] = {
        ItemFaction.WARDENS: 0,
        ItemFaction.COLONIALS: 0,
    }
    for candidates, _crated, _qty in resolved:
        if len(candidates) == 1 and candidates[0].faction in faction_votes:
            faction_votes[candidates[0].faction] += 1
    faction = _infer_faction(faction_votes)

    # Pass 2: pick a final code per item, using the faction to break collisions.
    items: list[StockpileItem] = [
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

    # Convert the localized region name from the export to its stable hex code;
    # an unrecognized region (e.g. one added before the enum is updated) keeps
    # its display name rather than collapsing to "Undefined".
    resolved_hex = Hex.from_display(header.hex)
    hex_name = header.hex if resolved_hex is Hex.UNDEFINED else resolved_hex.value

    # The faction is inferred by majority vote of the items; only a definite
    # side is reported. A NEUTRAL inference means we could not determine it, so
    # the faction is left unset rather than reported as neutral.
    inferred_faction = faction if faction in (ItemFaction.WARDENS, ItemFaction.COLONIALS) else None

    fields: dict[str, Any] = {
        "name": header.name,
        "type": header.type,
        "faction": inferred_faction,
        "hex": hex_name,
        "coords": header.coords,
        "items": items,
    }
    if header.timestamp is not None:
        fields["timestamp"] = header.timestamp

    return Stockpile(**fields)
