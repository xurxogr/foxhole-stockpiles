"""Tests for the catalog field rule engine.

The most important test is the retained round-trip safety net: the FS preset must
produce a catalog behaviourally identical to the full one for the two consumers
(template-DB ``CatalogItem`` and clipboard ``build_code_map``).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from foxhole_stockpiles.models.catalog_item import CatalogItem
from foxhole_stockpiles.services.clipboard_parser import build_code_map
from fs_tools.services.catalog_builder import (
    CatalogPreset,
    CatalogRule,
    CatalogRuleSet,
    RuleAction,
    apply_rules,
    detect_preset,
    load_ruleset,
    missing_required_paths,
    preset_ruleset,
    save_ruleset,
)

CATALOG_PATH = Path(__file__).resolve().parents[3].parent / "data" / "catalog.json"


def _ruleset(*pairs: tuple[str, str]) -> CatalogRuleSet:
    """Build a rule set from (action, pattern) string pairs.

    Args:
        *pairs (tuple[str, str]): (action, pattern) tuples.

    Returns:
        CatalogRuleSet: The assembled rule set.
    """
    return CatalogRuleSet(rules=[CatalogRule(action=RuleAction(a), pattern=p) for a, p in pairs])


def _sample_item() -> dict[str, Any]:
    """A full catalog entry carrying kept and dropped, scalar and nested fields.

    Returns:
        dict[str, Any]: A representative full catalog item.
    """
    return {
        "CodeName": "RifleC",
        "FactionVariant": "EFactionId::Colonials",
        "DisplayName": "Argenti r.II Rifle",
        "DisplayNameLocales": {"en": "Argenti r.II Rifle", "de": "Argenti r.II Gewehr"},
        "Icon": "War/Content/Textures/UI/ItemIcons/RifleIcon.0",
        "ItemProfileData": {"bIsCratable": True, "bIsCriticalToVictory": False},
        "Description": "A rifle.",
        "AmmoDynamicData": {"DamageType": {"Type": "Foo"}},
    }


# ===== Matching / ordering =====


def test_empty_ruleset_keeps_everything() -> None:
    """An empty rule set is identity (the FULL preset)."""
    catalog = [_sample_item()]
    assert apply_rules(catalog, CatalogRuleSet()) is catalog


def test_last_match_wins() -> None:
    """The last rule covering a leaf decides; default keeps."""
    rules = _ruleset(("exclude", "**"), ("include", "CodeName"))
    [item] = apply_rules([_sample_item()], rules)
    assert item == {"CodeName": "RifleC"}


def test_single_star_matches_one_segment() -> None:
    """``*`` matches exactly one path segment."""
    rules = _ruleset(("exclude", "ItemProfileData.*"))
    [item] = apply_rules([_sample_item()], rules)
    assert "ItemProfileData" not in item
    assert item["CodeName"] == "RifleC"  # untouched


def test_double_star_matches_subtree_but_not_self() -> None:
    """``X.**`` drops descendants of X but not a scalar X."""
    item = {"ShippableInfo": "EShippableType::Large", "Other": {"a": 1, "b": 2}}
    rules = _ruleset(("exclude", "Other.**"))
    [projected] = apply_rules([item], rules)
    assert projected == {"ShippableInfo": "EShippableType::Large"}


def test_prefix_include_keeps_whole_subtree() -> None:
    """Including an ancestor keeps the whole subtree."""
    rules = _ruleset(("exclude", "**"), ("include", "DisplayNameLocales"))
    [item] = apply_rules([_sample_item()], rules)
    assert item == {"DisplayNameLocales": {"en": "Argenti r.II Rifle", "de": "Argenti r.II Gewehr"}}


def test_apply_rules_does_not_mutate_input() -> None:
    """Projection never mutates the source catalog."""
    catalog = [_sample_item()]
    apply_rules(catalog, preset_ruleset(CatalogPreset.FS))
    assert catalog == [_sample_item()]


# ===== Presets =====


def test_full_preset_is_empty() -> None:
    """The FULL preset has no rules (keep everything)."""
    assert preset_ruleset(CatalogPreset.FULL).rules == []


def test_fs_preset_trims_to_minimum() -> None:
    """The FS preset drops unused fields and deep-prunes containers."""
    [item] = apply_rules([_sample_item()], preset_ruleset(CatalogPreset.FS))
    assert "Description" not in item
    assert "AmmoDynamicData" not in item
    assert item["ItemProfileData"] == {"bIsCratable": True}


def test_fs_preset_keeps_scalar_shippable_info() -> None:
    """The FS preset keeps a scalar ShippableInfo marker."""
    item = {"CodeName": "Air", "ShippableInfo": "EShippableType::Large"}
    [projected] = apply_rules([item], preset_ruleset(CatalogPreset.FS))
    assert projected["ShippableInfo"] == "EShippableType::Large"


def test_fs_preset_reduces_dict_shippable_info() -> None:
    """The FS preset reduces a dict ShippableInfo to the one used sub-key."""
    item = {"CodeName": "X", "ShippableInfo": {"bAllowPackagingToCrate": True, "Noise": 1}}
    [projected] = apply_rules([item], preset_ruleset(CatalogPreset.FS))
    assert projected["ShippableInfo"] == {"bAllowPackagingToCrate": True}


def test_detect_preset() -> None:
    """detect_preset recognises preset rule sets and flags custom ones."""
    assert detect_preset(preset_ruleset(CatalogPreset.FULL)) is CatalogPreset.FULL
    assert detect_preset(preset_ruleset(CatalogPreset.FS)) is CatalogPreset.FS
    assert detect_preset(_ruleset(("exclude", "CodeName"))) is None


# ===== Validation =====


def test_presets_satisfy_required_minimum() -> None:
    """Both presets keep the full required minimum (no warning)."""
    assert missing_required_paths(preset_ruleset(CatalogPreset.FULL)) == []
    assert missing_required_paths(preset_ruleset(CatalogPreset.FS)) == []


def test_missing_required_reports_dropped_field() -> None:
    """Dropping a required field is reported."""
    rules = list(preset_ruleset(CatalogPreset.FS).rules)
    rules = [r for r in rules if r.pattern != "CodeName"]
    missing = missing_required_paths(CatalogRuleSet(rules=rules))
    assert "CodeName" in missing


# ===== Serialization =====


def test_ruleset_round_trips_through_file(tmp_path: Path) -> None:
    """save_ruleset then load_ruleset preserves the rule set."""
    ruleset = preset_ruleset(CatalogPreset.FS)
    path = tmp_path / "rules.json"
    save_ruleset(path, ruleset)
    assert load_ruleset(path).rules == ruleset.rules


def test_load_ruleset_rejects_bad_json(tmp_path: Path) -> None:
    """load_ruleset raises ValueError on invalid content."""
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_ruleset(path)


# ===== Round-trip safety net over the shipped catalog =====


@pytest.fixture
def full_catalog() -> list[dict[str, Any]]:
    """Load the real shipped catalog.

    Returns:
        list[dict[str, Any]]: The full catalog entries.
    """
    if not CATALOG_PATH.exists():
        pytest.skip(f"catalog.json not found at {CATALOG_PATH}")
    with CATALOG_PATH.open(encoding="utf-8") as f:
        catalog: list[dict[str, Any]] = json.load(f)
    return catalog


def test_fs_preset_round_trips_catalog_item(full_catalog: list[dict[str, Any]]) -> None:
    """FS yields identical CatalogItem objects as the full catalog (DB consumer)."""
    fs_catalog = apply_rules(full_catalog, preset_ruleset(CatalogPreset.FS))
    assert len(fs_catalog) == len(full_catalog)
    for full_item, fs_item in zip(full_catalog, fs_catalog, strict=True):
        assert CatalogItem.from_catalog(full_item) == CatalogItem.from_catalog(fs_item)


def test_fs_preset_round_trips_code_map(full_catalog: list[dict[str, Any]]) -> None:
    """FS yields an identical clipboard code map as the full catalog."""
    fs_catalog = apply_rules(full_catalog, preset_ruleset(CatalogPreset.FS))
    full_map = build_code_map(full_catalog)
    fs_map = build_code_map(fs_catalog)
    for locale in full_map.locales:
        for item in full_catalog:
            for name in (item.get("DisplayNameLocales") or {}).values():
                assert full_map.resolve(name, locale) == fs_map.resolve(name, locale)
