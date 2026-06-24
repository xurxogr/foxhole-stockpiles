"""Tests for the clipboard stockpile-export parser."""

from pathlib import Path
from typing import Any

import pytest

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.services.clipboard_parser import (
    ClipboardCodeMap,
    _infer_faction,
    build_code_map,
    build_code_map_from_file,
    parse_clipboard,
)

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "catalog.json"

# A representative export: header, a crated small-items group, a blank-line
# group boundary, an assembled-vehicles group, then a crated group containing
# the one ambiguous name ("Rare Materials"). Uses the in-game curly glyphs.
SAMPLE = (
    "Terminus - Rising Loom - Seaport - Public - X: 0.4577449 Y: 0.6644695,2026.06.23-16.30.38\n"
    "Argenti r.II Rifle (Crate),32\n"
    "Booker Storm Rifle Model 838 (Crate),0\n"
    "7.62mm (Crate),60\n"
    "No.2 Loughcaster (Crate),0\n"
    "Tripod (Crate),38\n"
    "\n"
    "O’Brien V.101 Freeman,2\n"
    "T3 “Xiphos”,0\n"
    "\n"
    "Rare Materials (Crate),5\n"
    "Mortar Shell (Crate),56\n"
)


@pytest.fixture(scope="module")
def code_map() -> ClipboardCodeMap:
    """Build a code map from the real project catalog.

    Returns:
        ClipboardCodeMap: The catalog-backed code map.
    """
    return build_code_map_from_file(CATALOG_PATH)


def test_returns_none_for_non_stockpile_text(code_map: ClipboardCodeMap) -> None:
    """Arbitrary clipboard text is not parsed (the monitor gate)."""
    assert parse_clipboard("just some copied text\nwith lines", code_map) is None
    assert parse_clipboard("", code_map) is None
    assert parse_clipboard(None, code_map) is None


def test_parses_header_fields(code_map: ClipboardCodeMap) -> None:
    """Header maps to hex, type, name, and coords (town/city dropped)."""
    stockpile = parse_clipboard(SAMPLE, code_map)
    assert stockpile is not None
    assert stockpile.hex == "TerminusHex"
    assert stockpile.type == StockpileType.SEAPORT
    assert stockpile.name == "Public"
    assert stockpile.coords is not None
    assert stockpile.coords.x == pytest.approx(0.4577449)
    assert stockpile.coords.y == pytest.approx(0.6644695)


def test_parses_export_timestamp(code_map: ClipboardCodeMap) -> None:
    """The UTC export timestamp populates the stockpile timestamp."""
    stockpile = parse_clipboard(SAMPLE, code_map)
    assert stockpile is not None
    assert stockpile.timestamp.year == 2026
    assert stockpile.timestamp.month == 6
    assert stockpile.timestamp.day == 23
    assert (stockpile.timestamp.hour, stockpile.timestamp.minute) == (16, 30)


def test_filters_zero_quantities_and_maps_codes(code_map: ClipboardCodeMap) -> None:
    """Only items with quantity >= 1 are kept, mapped to catalog codes."""
    stockpile = parse_clipboard(SAMPLE, code_map)
    assert stockpile is not None
    by_code = {item.code: item for item in stockpile.items}

    # Kept (>= 1) and correctly coded.
    assert by_code["RifleC"].quantity == 32
    assert by_code["RifleAmmo"].quantity == 60
    assert by_code["Tripod"].quantity == 38
    assert by_code["MortarAmmo"].quantity == 56

    # Dropped (quantity 0).
    assert "RifleW" not in by_code  # No.2 Loughcaster (Crate),0


def test_crate_suffix_sets_crated_flag(code_map: ClipboardCodeMap) -> None:
    """The ` (Crate)` suffix marks the item crated; bare names are not."""
    stockpile = parse_clipboard(SAMPLE, code_map)
    assert stockpile is not None
    by_code = {item.code: item for item in stockpile.items}

    assert by_code["RifleC"].crated is True  # "... (Crate)"
    assert by_code["ArmoredCar2LargeW"].crated is False  # bare vehicle line


def test_quote_normalization_matches_curly_names(code_map: ClipboardCodeMap) -> None:
    """Curly apostrophes/quotes in the export match catalog display names."""
    stockpile = parse_clipboard(SAMPLE, code_map)
    assert stockpile is not None
    by_code = {item.code: item for item in stockpile.items}
    # O’Brien V.101 Freeman (curly apostrophe) resolves to its code.
    assert by_code["ArmoredCar2LargeW"].quantity == 2


def test_ambiguous_rare_materials_prefers_base_code(code_map: ClipboardCodeMap) -> None:
    """The one duplicate display name resolves to the base-resource code."""
    stockpile = parse_clipboard(SAMPLE, code_map)
    assert stockpile is not None
    codes = {item.code for item in stockpile.items}
    assert "RareMaterials" in codes
    assert "FacilityMaterials12" not in codes


def test_build_code_map_records_faction() -> None:
    """The code map carries each item's faction for the majority vote."""
    catalog: list[dict[str, Any]] = [
        {
            "CodeName": "RifleC",
            "DisplayName": "Argenti r.II Rifle",
            "FactionVariant": "EFactionId::Colonials",
        },
        {
            "CodeName": "RifleW",
            "DisplayName": "No.2 Loughcaster",
            "FactionVariant": "EFactionId::Wardens",
        },
        {"CodeName": "RifleAmmo", "DisplayName": "7.62mm", "FactionVariant": None},
    ]
    code_map = build_code_map(catalog)

    colonial = code_map.resolve("Argenti r.II Rifle")
    warden = code_map.resolve("No.2 Loughcaster")
    neutral = code_map.resolve("7.62mm")
    assert colonial is not None and colonial.faction == ItemFaction.COLONIALS
    assert warden is not None and warden.faction == ItemFaction.WARDENS
    assert neutral is not None and neutral.faction == ItemFaction.NEUTRAL
    assert code_map.resolve("Nonexistent Item") is None


def test_detects_language_and_maps_localized_names() -> None:
    """A non-English export is detected and read in its language."""
    catalog: list[dict[str, Any]] = [
        {
            "CodeName": "Bandages",
            "DisplayName": "Bandages",
            "DisplayNameLocales": {"en": "Bandages", "de": "Verbände"},
        },
        {
            "CodeName": "Water",
            "DisplayName": "Water",
            "DisplayNameLocales": {"en": "Water", "de": "Wasser"},
        },
        {
            "CodeName": "RifleAmmo",
            "DisplayName": "7.62mm",
            "DisplayNameLocales": {"en": "7.62mm", "de": "7.62mm"},
        },
    ]
    code_map = build_code_map(catalog)
    # German export: localized names, a German crate word, German type.
    text = (
        "Hex - Stadt - Seehafen - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n"
        "Verbände (Kiste),5\n"
        "Wasser,3\n"
        "7.62mm (Kiste),0\n"
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    assert stockpile.type == StockpileType.SEAPORT  # "Seehafen"
    by_code = {item.code: item for item in stockpile.items}
    assert by_code["Bandages"].quantity == 5
    assert by_code["Bandages"].crated is True  # "(Kiste)" detected structurally
    assert by_code["Water"].quantity == 3
    assert by_code["Water"].crated is False
    assert "RifleAmmo" not in by_code  # quantity 0 filtered


def test_untranslated_item_falls_back_to_english_in_localized_export() -> None:
    """An item with no translation appears in English even in a localized file."""
    catalog: list[dict[str, Any]] = [
        {
            "CodeName": "Water",
            "DisplayName": "Water",
            "DisplayNameLocales": {"en": "Water", "de": "Wasser"},
        },
        {
            "CodeName": "RareMaterials",
            "DisplayName": "Rare Materials",
            "DisplayNameLocales": {"en": "Rare Materials"},
        },  # English-only
    ]
    code_map = build_code_map(catalog)
    text = (
        "Hex - Stadt - Seehafen - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n"
        "Wasser (Kiste),2\n"
        "Rare Materials (Kiste),5\n"  # untranslated -> English name in a German export
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    by_code = {item.code: item for item in stockpile.items}
    assert by_code["Water"].quantity == 2
    assert by_code["RareMaterials"].quantity == 5
    assert by_code["RareMaterials"].crated is True


def test_real_catalog_german_export(code_map: ClipboardCodeMap) -> None:
    """A German export against the real catalog resolves localized names."""
    text = (
        "Hex - Stadt - Seehafen - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n"
        "Wasser (Kiste),46\n"
        "Verbände (Kiste),18\n"
        "950-70b Luftabwehrgranate (Kiste),5\n"
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    by_code = {item.code: item for item in stockpile.items}
    assert by_code["Water"].quantity == 46
    assert by_code["Bandages"].quantity == 18
    assert by_code["AAAmmo"].quantity == 5
    assert by_code["AAAmmo"].crated is True


@pytest.mark.parametrize(
    ("majority_item", "majority_faction_code", "expected_uniform"),
    [
        ("No.2 Loughcaster", "RifleW", "MedicUniformW"),
        ("Argenti r.II Rifle", "RifleC", "MedicUniformC"),
    ],
)
def test_faction_majority_disambiguates_localized_collision(
    majority_item: str, majority_faction_code: str, expected_uniform: str
) -> None:
    """A faction-distinguishable localized name collision resolves by majority.

    The German "Sanitäter Uniform" maps to both faction uniforms; the side that
    most items belong to decides which one a given stockpile gets.
    """
    catalog: list[dict[str, Any]] = [
        {
            "CodeName": "MedicUniformC",
            "DisplayNameLocales": {"en": "Medic Fatigues", "de": "Sanitäter Uniform"},
            "FactionVariant": "EFactionId::Colonials",
        },
        {
            "CodeName": "MedicUniformW",
            "DisplayNameLocales": {"en": "Physician's Jacket", "de": "Sanitäter Uniform"},
            "FactionVariant": "EFactionId::Wardens",
        },
        {
            "CodeName": "RifleW",
            "DisplayNameLocales": {"en": "No.2 Loughcaster", "de": "No.2 Loughcaster"},
            "FactionVariant": "EFactionId::Wardens",
        },
        {
            "CodeName": "RifleC",
            "DisplayNameLocales": {"en": "Argenti r.II Rifle", "de": "Argenti r.II Rifle"},
            "FactionVariant": "EFactionId::Colonials",
        },
    ]
    code_map = build_code_map(catalog)
    # German export; the chosen rifle makes one faction the majority.
    text = (
        "Hex - Stadt - Seehafen - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n"
        "Sanitäter Uniform (Kiste),5\n"
        f"{majority_item} (Kiste),9\n"
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    codes = {item.code for item in stockpile.items}
    assert expected_uniform in codes
    assert majority_faction_code in codes


def test_inferred_faction_surfaced_on_stockpile() -> None:
    """A clear item-faction majority is reported as the stockpile faction."""
    catalog: list[dict[str, Any]] = [
        {
            "CodeName": "RifleC",
            "DisplayNameLocales": {"en": "Argenti r.II Rifle"},
            "FactionVariant": "EFactionId::Colonials",
        },
    ]
    code_map = build_code_map(catalog)
    text = (
        "Hex - Town - Seaport - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n"
        "Argenti r.II Rifle (Crate),5\n"
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    assert stockpile.faction == ItemFaction.COLONIALS


def test_neutral_inference_leaves_faction_none() -> None:
    """Only neutral items → faction cannot be determined → None (omitted)."""
    catalog: list[dict[str, Any]] = [
        {
            "CodeName": "RifleAmmo",
            "DisplayNameLocales": {"en": "7.62mm"},
            "FactionVariant": None,
        },
    ]
    code_map = build_code_map(catalog)
    text = "Hex - Town - Seaport - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n7.62mm (Crate),60\n"
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    assert stockpile.faction is None


def test_hex_display_name_converted_to_code(code_map: ClipboardCodeMap) -> None:
    """A region display name (incl. curly apostrophe) resolves to its hex code."""
    text = (
        "Callahan’s Passage - Town - Seaport - Public - X: 0.1 Y: 0.2,"
        "2026.06.23-16.30.38\n"
        "Argenti r.II Rifle (Crate),5\n"
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    assert stockpile.hex == "CallahansPassageHex"


def test_unknown_hex_keeps_display_name(code_map: ClipboardCodeMap) -> None:
    """A region not in the enum keeps its display name instead of 'Undefined'."""
    text = (
        "Atlantis - Town - Seaport - Public - X: 0.1 Y: 0.2,2026.06.23-16.30.38\n"
        "Argenti r.II Rifle (Crate),5\n"
    )
    stockpile = parse_clipboard(text, code_map)
    assert stockpile is not None
    assert stockpile.hex == "Atlantis"


def test_infer_faction_majority() -> None:
    """Faction inference takes the side with the most non-neutral items."""
    assert _infer_faction({ItemFaction.WARDENS: 5, ItemFaction.COLONIALS: 2}) == ItemFaction.WARDENS
    assert (
        _infer_faction({ItemFaction.WARDENS: 1, ItemFaction.COLONIALS: 9}) == ItemFaction.COLONIALS
    )
    assert _infer_faction({ItemFaction.WARDENS: 3, ItemFaction.COLONIALS: 3}) == ItemFaction.NEUTRAL
