"""Parse Foxhole in-game stockpile clipboard exports into runtime ``Stockpile``.

The in-game "copy stockpile" feature places a text block on the clipboard with
this shape::

    Hex - Town - Type - Name - X: <x> Y: <y>,<UTC timestamp>
    <Item Display Name> (Crate),<quantity>
    ...

    <next group>
    ...

Lines are grouped by category, each group separated by a blank line, and the
groups always appear in the same order. Each item line carries an explicit
crate suffix when crated. Only items with a quantity of 1 or more are kept.

**Localization.** The export is in the game's language: item names, the crate
suffix, and the stockpile type are all localized. The parser therefore:

* maps item names against every locale in the catalog and *detects* the export
  language from the items themselves (the language that explains the most
  lines), so the rest of the file is read in that language;
* falls back to English per item, because untranslated items appear in English
  even within a localized export;
* detects "crated" structurally — an item is crated when the name only resolves
  after dropping its trailing parenthetical (the localized crate word) — so no
  per-language crate vocabulary is needed, and inherent parentheticals such as
  "(Small)" are preserved.

This module is the clipboard analogue of :mod:`services.scanner`: it adapts an
externally-defined format into the runtime :class:`Stockpile` model. It is pure
(no I/O): callers pass the clipboard text and a :class:`ClipboardCodeMap` built
from the item catalog. ``parse_clipboard`` returns ``None`` when the text is not
a stockpile export, which is the gate the monitor uses to ignore unrelated
clipboard content.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem

logger = logging.getLogger(__name__)

# In-game export timestamp, e.g. "2026.06.23-16.30.38".
_TIMESTAMP_FORMAT = "%Y.%m.%d-%H.%M.%S"

# Locale used as the universal fallback: every catalog item has an English name,
# and untranslated items appear in English even within a localized export.
_FALLBACK_LOCALE = "en"

# Header line: "<hex> - <town> - <type> - <name> - X: <x> Y: <y>,<timestamp>".
# The coords/timestamp tail is unambiguous (and not localized), so anchor on it
# and treat the rest as the " - "-joined prefix.
_HEADER_RE = re.compile(
    r"^(?P<prefix>.+) - X:\s*(?P<x>[-+]?\d*\.?\d+)\s+Y:\s*(?P<y>[-+]?\d*\.?\d+),(?P<ts>.+)$"
)

# A name ending in a parenthetical group, e.g. "Foo (Crate)" -> base "Foo".
# Only the last group is captured, so "Foo (Small) (Crate)" -> "Foo (Small)".
_TRAILING_PAREN_RE = re.compile(r"^(?P<base>.*\S)\s*\([^()]*\)\s*$")

# Typographic glyphs the in-game names use, normalized so clipboard text and
# catalog display names compare equal regardless of which form either uses.
_QUOTE_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "´": "'",
        "`": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "″": '"',
    }
)

# Stockpile type display names (in any game language) -> runtime type. Type
# names do not collide across languages, so a single flat map is
# language-agnostic. Unknown types fall back to UNDEFINED.
_TYPE_ALIASES: list[tuple[StockpileType, tuple[str, ...]]] = [
    (StockpileType.SEAPORT, ("Seaport", "Seehafen", "Port", "Porto", "Морской порт", "海港")),
    (
        StockpileType.STORAGE_DEPOT,
        ("Storage Depot", "Lagerdepot", "Dépôt", "Depósito", "Складское помещение", "仓库"),
    ),
    (StockpileType.AIRCRAFT_DEPOT, ("Aircraft Depot",)),
    (
        StockpileType.ENCAMPMENT,
        ("Encampment", "Feldlager", "Campement", "Acampamento", "Лагерь", "营地"),
    ),
    (StockpileType.KEEP, ("Keep", "Wehrturm", "Place Forte", "Torreão", "Крепость", "要塞")),
    (
        StockpileType.SAFE_HOUSE,
        ("Safe House", "Unterschlupf", "Planque", "Casa Fortificada", "Убежище", "安全屋"),
    ),
    (
        StockpileType.RELIC_BASE,
        (
            "Relic Base",
            "Reliktbasis",
            "Base Relique",
            "Base Relíquia",
            "Реликтовая База",
            "遗迹基地",
        ),
    ),
    (
        StockpileType.BUNKER_BASE_1,
        (
            "Bunker Base",
            "Bunkerbasis",
            "Base Bunker",
            "Centro do Bunker",
            "Бункерная база",
            "地堡基地",
        ),
    ),
    (
        StockpileType.BORDER_BASE,
        (
            "Border Base",
            "Grenzbasis",
            "Base Frontalière",
            "Base Fronteiriça",
            "Пограничная База",
            "边境基地",
        ),
    ),
    (
        StockpileType.TOWN_BASE_1,
        (
            "Town Base",
            "Town Hall",
            "Stadtkernbasis",
            "Quartier Général",
            "Base da Cidade",
            "Ратуша",
            "城镇基地",
        ),
    ),
    (
        StockpileType.UNDERGROUND_FORTRESS,
        (
            "Underground Fortress",
            "Untergrundfestung",
            "Forteresse Souterraine",
            "Bunker Subterrâneo",
            "Подземная Крепость",
            "地下要塞",
        ),
    ),
]
_TYPE_BY_DISPLAY: dict[str, StockpileType] = {
    name.lower(): stockpile_type for stockpile_type, names in _TYPE_ALIASES for name in names
}

# The catalog has exactly one duplicate display name ("Rare Materials" maps to
# both ``RareMaterials`` and ``FacilityMaterials12``, both faction-neutral).
# Prefer the base-resource code so all sources agree on a single mapping.
_PREFERRED_CODES: frozenset[str] = frozenset({"RareMaterials"})


def _normalize(text: str) -> str:
    """Normalize typographic quotes and surrounding whitespace.

    Args:
        text (str): Raw text from clipboard or catalog.

    Returns:
        str: Text with curly quotes/apostrophes folded to ASCII and trimmed.
    """
    return text.translate(_QUOTE_TRANSLATION).strip()


@dataclass(frozen=True)
class CatalogCode:
    """A catalog item's code and faction, used for clipboard code-mapping."""

    code: str
    faction: ItemFaction


class ClipboardCodeMap:
    """Maps a localized item display name to its catalog code (and faction).

    Names are indexed per locale so the export language can be detected and the
    whole file read in that language, always with an English fallback.
    """

    def __init__(self, by_locale: dict[str, dict[str, list[CatalogCode]]]) -> None:
        """Initialize the code map.

        Args:
            by_locale (dict[str, dict[str, list[CatalogCode]]]): Locale code to a
                map of normalized display name -> the catalog codes sharing it.
        """
        self._by_locale = by_locale

    @property
    def locales(self) -> list[str]:
        """Return the available locales, English first then the rest sorted.

        Returns:
            list[str]: Locale codes, biased so English wins detection ties.
        """
        others = sorted(loc for loc in self._by_locale if loc != _FALLBACK_LOCALE)
        head = [_FALLBACK_LOCALE] if _FALLBACK_LOCALE in self._by_locale else []
        return head + others

    def candidates(self, display_name: str, locale: str | None = None) -> list[CatalogCode]:
        """Return all catalog codes a display name maps to.

        Usually a single code; more than one only for the rare catalog
        collisions (e.g. faction-distinguishable names that coincide in a
        locale). Caller decides how to disambiguate.

        Args:
            display_name (str): Item display name (without any crate suffix).
            locale (str | None): Locale to resolve in (English fallback always
                applies). When None, every locale is searched.

        Returns:
            list[CatalogCode]: The matching codes, or an empty list if unknown.
        """
        key = _normalize(display_name)
        if locale is None:
            search = self.locales
        else:
            search = [locale]
            if locale != _FALLBACK_LOCALE:
                search.append(_FALLBACK_LOCALE)

        for loc in search:
            matches = self._by_locale.get(loc, {}).get(key)
            if matches:
                return matches
        return []

    def resolve(self, display_name: str, locale: str | None = None) -> CatalogCode | None:
        """Resolve a display name to a single catalog code (collisions aside).

        Args:
            display_name (str): Item display name (without any crate suffix).
            locale (str | None): Locale to resolve in (English fallback always
                applies). When None, every locale is searched.

        Returns:
            CatalogCode | None: The matched code, or None if the name is unknown.
        """
        matches = self.candidates(display_name, locale)
        return _choose_code(matches) if matches else None


def _choose_code(matches: list[CatalogCode]) -> CatalogCode:
    """Choose one code deterministically from same-name candidates.

    Args:
        matches (list[CatalogCode]): Non-empty candidate codes for a name.

    Returns:
        CatalogCode: The preferred code, else the lowest code name (stable).
    """
    if len(matches) == 1:
        return matches[0]
    preferred = [m for m in matches if m.code in _PREFERRED_CODES]
    return (preferred or sorted(matches, key=lambda m: m.code))[0]


def build_code_map(catalog: list[dict[str, Any]]) -> ClipboardCodeMap:
    """Build a per-locale display-name -> code map from catalog entries.

    Args:
        catalog (list[dict[str, Any]]): Parsed ``catalog.json`` entries.

    Returns:
        ClipboardCodeMap: The reverse lookup map keyed by locale and name.
    """
    by_locale: dict[str, dict[str, list[CatalogCode]]] = defaultdict(lambda: defaultdict(list))
    for item in catalog:
        code = item.get("CodeName")
        if not code:
            continue
        entry = CatalogCode(code=code, faction=ItemFaction.from_string(item.get("FactionVariant")))

        names: dict[str, str] = dict(item.get("DisplayNameLocales") or {})
        # Ensure an English name exists (the universal fallback).
        if _FALLBACK_LOCALE not in names and item.get("DisplayName"):
            names[_FALLBACK_LOCALE] = item["DisplayName"]

        for locale, name in names.items():
            if name:
                by_locale[locale][_normalize(name)].append(entry)

    _log_collisions(by_locale)

    # Freeze the defaultdicts into plain dicts.
    return ClipboardCodeMap({loc: dict(names) for loc, names in by_locale.items()})


def _log_collisions(by_locale: dict[str, dict[str, list[CatalogCode]]]) -> None:
    """Log, once, any display name that maps to more than one catalog code.

    Collisions are a property of the catalog (e.g. "Rare Materials"), so they
    are reported a single time when the map is built rather than on every
    lookup.

    Args:
        by_locale (dict[str, dict[str, list[CatalogCode]]]): The locale->name->
            codes index being built.
    """
    reported: set[tuple[str, ...]] = set()
    for names in by_locale.values():
        for name, matches in names.items():
            if len(matches) < 2:
                continue
            codes = tuple(sorted(m.code for m in matches))
            if codes in reported:
                continue
            reported.add(codes)
            logger.warning(
                "Catalog display name %r maps to multiple codes %s; using %r",
                name,
                list(codes),
                _choose_code(matches).code,
            )


def build_code_map_from_file(catalog_path: Path) -> ClipboardCodeMap:
    """Build a code map from a ``catalog.json`` file.

    Args:
        catalog_path (Path): Path to the catalog JSON file.

    Returns:
        ClipboardCodeMap: The reverse lookup map.

    Raises:
        FileNotFoundError: If the catalog file does not exist.
    """
    with catalog_path.open(encoding="utf-8") as f:
        catalog = json.load(f)
    return build_code_map(catalog)


@dataclass(frozen=True)
class _Header:
    """Parsed header line fields (town/city intentionally dropped)."""

    hex: str
    type: StockpileType
    name: str
    coords: StockpileCoords
    timestamp: datetime | None


def _type_from_display(display: str) -> StockpileType:
    """Map an exported stockpile type display name (any language) to a type.

    Args:
        display (str): The type field from the header (e.g. "Seaport").

    Returns:
        StockpileType: The matching type, or UNDEFINED when unknown.
    """
    stockpile_type = _TYPE_BY_DISPLAY.get(_normalize(display).lower())
    if stockpile_type is None:
        logger.debug("Unknown stockpile type in clipboard header: %r", display)
        return StockpileType.UNDEFINED
    return stockpile_type


def _parse_header(line: str) -> _Header | None:
    """Parse the header line; the gate for "is this a stockpile export".

    Args:
        line (str): The candidate header line.

    Returns:
        _Header | None: Parsed header, or None if the line is not a header.
    """
    match = _HEADER_RE.match(line.strip())
    if not match:
        return None

    parts = [p.strip() for p in match.group("prefix").split(" - ")]
    if len(parts) < 3:
        return None

    # parts: [hex, town, type, name...]. The town/city is dropped. The name may
    # itself contain " - ", so any extra segments are folded back into it.
    hex_name = parts[0]
    type_display = parts[2]
    name = " - ".join(parts[3:]) if len(parts) > 3 else ""

    try:
        coords = StockpileCoords(x=float(match.group("x")), y=float(match.group("y")))
    except ValueError:
        return None

    timestamp: datetime | None = None
    try:
        timestamp = datetime.strptime(match.group("ts").strip(), _TIMESTAMP_FORMAT)
    except ValueError:
        logger.debug("Could not parse clipboard timestamp: %r", match.group("ts"))

    return _Header(
        hex=hex_name,
        type=_type_from_display(type_display),
        name=name,
        coords=coords,
        timestamp=timestamp,
    )


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

    fields: dict[str, Any] = {
        "name": header.name,
        "type": header.type,
        "hex": header.hex,
        "coords": header.coords,
        "items": items,
    }
    if header.timestamp is not None:
        fields["timestamp"] = header.timestamp

    return Stockpile(**fields)


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
