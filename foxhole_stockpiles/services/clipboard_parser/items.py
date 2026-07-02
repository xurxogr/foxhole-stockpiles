"""Parsing and resolving of the clipboard export's item lines."""

from __future__ import annotations

import re

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.services.clipboard_parser.code_map import (
    CatalogCode,
    ClipboardCodeMap,
    _choose_code,
)

# A name ending in a parenthetical group, e.g. "Foo (Crate)" -> base "Foo".
# Only the last group is captured, so "Foo (Small) (Crate)" -> "Foo (Small)".
_TRAILING_PAREN_RE = re.compile(r"^(?P<base>.*\S)\s*\([^()]*\)\s*$")


def _parse_item_line(line: str) -> tuple[str, int] | None:
    """Parse an item line into ``(display_name, quantity)``.

    Args:
        line (str): A non-empty body line, e.g. "Argenti r.II Rifle (Crate),32".

    Returns:
        tuple[str, int] | None: The display name and quantity, or None if the
            line is not a valid item line.
    """
    name, sep, qty_text = line.rpartition(",")
    if not sep:
        return None
    try:
        quantity = int(qty_text.strip())
    except ValueError:
        return None
    return name.strip(), quantity


def _resolve_item_candidates(
    code_map: ClipboardCodeMap, display: str, locale: str | None
) -> tuple[list[CatalogCode], bool]:
    """Resolve an item display (possibly crated) to its candidates and crate flag.

    Crated state is detected structurally: if the full name does not resolve but
    the name without its trailing parenthetical does, the item is crated and the
    parenthetical was the (localized) crate word.

    Args:
        code_map (ClipboardCodeMap): The catalog code map.
        display (str): The raw item display name from the export.
        locale (str | None): The detected export locale (English fallback applies).

    Returns:
        tuple[list[CatalogCode], bool]: The matching codes (empty if unknown) and
            whether the item is crated.
    """
    direct = code_map.candidates(display, locale)
    if direct:
        return direct, False

    trailing = _TRAILING_PAREN_RE.match(display)
    if trailing is not None:
        crated = code_map.candidates(trailing.group("base"), locale)
        if crated:
            return crated, True

    return [], False


def _select_code(candidates: list[CatalogCode], faction: ItemFaction) -> CatalogCode:
    """Pick one code from candidates, using the stockpile faction on collisions.

    The common case is a single candidate. When a name collides on
    faction-distinguishable codes (e.g. the German "Sanitäter Uniform" maps to
    both the Colonial and Warden uniform), the inferred stockpile faction breaks
    the tie; otherwise a deterministic fallback is used.

    Args:
        candidates (list[CatalogCode]): The non-empty candidate codes.
        faction (ItemFaction): The inferred stockpile faction.

    Returns:
        CatalogCode: The chosen code.
    """
    if len(candidates) == 1:
        return candidates[0]
    if faction in (ItemFaction.WARDENS, ItemFaction.COLONIALS):
        same_faction = [c for c in candidates if c.faction == faction]
        if same_faction:
            return _choose_code(same_faction)
    return _choose_code(candidates)


def _detect_locale(code_map: ClipboardCodeMap, displays: list[str]) -> str | None:
    """Detect the export language from its item names.

    Scores each locale by how many item lines it resolves (English fallback
    included), and returns the best. A single early item is often enough; when
    the first items are ambiguous (e.g. language-invariant calibers), later
    items decide. English wins ties.

    Args:
        code_map (ClipboardCodeMap): The catalog code map.
        displays (list[str]): All item display names from the export body.

    Returns:
        str | None: The detected locale, or None if nothing resolved at all.
    """
    best_locale: str | None = None
    best_score = 0
    for locale in code_map.locales:
        score = sum(1 for d in displays if _resolve_item_candidates(code_map, d, locale)[0])
        if score > best_score:
            best_score = score
            best_locale = locale
    return best_locale


def _infer_faction(votes: dict[ItemFaction, int]) -> ItemFaction:
    """Infer the stockpile faction from a majority vote over its items.

    A stockpile may hold both factions' items even while controlled by one
    side, so the faction is the side with the most (non-neutral) items. The
    result is informational only and is not stored on the stockpile.

    Args:
        votes (dict[ItemFaction, int]): Item counts per faction.

    Returns:
        ItemFaction: The majority faction, or NEUTRAL on a tie or no votes.
    """
    wardens = votes.get(ItemFaction.WARDENS, 0)
    colonials = votes.get(ItemFaction.COLONIALS, 0)
    if wardens > colonials:
        return ItemFaction.WARDENS
    if colonials > wardens:
        return ItemFaction.COLONIALS
    return ItemFaction.NEUTRAL
