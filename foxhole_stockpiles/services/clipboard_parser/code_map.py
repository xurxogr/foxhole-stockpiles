"""Reverse lookup from a localized item display name to its catalog code."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foxhole_stockpiles.enums.item_faction import ItemFaction

logger = logging.getLogger(__name__)

# Locale used as the universal fallback: every catalog item has an English name,
# and untranslated items appear in English even within a localized export.
_FALLBACK_LOCALE = "en"

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
        """The available locales, English first then the rest sorted.

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
