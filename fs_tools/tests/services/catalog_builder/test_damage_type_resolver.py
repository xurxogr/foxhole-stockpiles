"""Tests for catalog_builder.damage_type_resolver module."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from fs_tools.services.catalog_builder.damage_type_resolver import (
    build_damage_type_result,
    get_ammo_code,
    resolve_damage_type,
)


@pytest.fixture
def data_service() -> MagicMock:
    """Create a mock DataTableLookup with no ammo/damage-type data by default."""
    mock = MagicMock()
    mock.get_ammo_dynamic_data.return_value = None
    return mock


@pytest.fixture
def loc_service() -> MagicMock:
    """Create a mock LocalizationLookup with GUID resolution disabled by default."""
    mock = MagicMock()
    mock.is_guid.return_value = False
    mock.get_with_fallback.side_effect = lambda guid: f"Resolved({guid})"
    mock.get_all_languages.return_value = {}
    return mock


class TestGetAmmoCode:
    """Tests for get_ammo_code."""

    def test_item_itself_is_ammo(self, data_service: MagicMock) -> None:
        """When the item's own CodeName has AmmoDynamicData, that CodeName is the ammo code."""
        data_service.get_ammo_dynamic_data.return_value = {"Damage": 5}
        data = {"CodeName": "RifleAmmo"}
        assert get_ammo_code(data=data, data_service=data_service) == "RifleAmmo"

    def test_no_item_component_class_returns_none(self, data_service: MagicMock) -> None:
        """With no ItemComponentClass dict, there's nothing to resolve ammo from."""
        assert get_ammo_code(data={"CodeName": "Foo"}, data_service=data_service) is None
        assert (
            get_ammo_code(
                data={"CodeName": "Foo", "ItemComponentClass": "not-a-dict"},
                data_service=data_service,
            )
            is None
        )

    def test_single_multi_ammo_entry(self, data_service: MagicMock) -> None:
        """A single-entry MultiAmmo list is used as the ammo code."""
        data = {"CodeName": "Weapon", "ItemComponentClass": {"MultiAmmo": ["RifleAmmo"]}}
        assert get_ammo_code(data=data, data_service=data_service) == "RifleAmmo"

    def test_multiple_multi_ammo_entries_not_used(self, data_service: MagicMock) -> None:
        """Multiple MultiAmmo entries are ambiguous, so they are not resolved here."""
        data = {
            "CodeName": "Weapon",
            "ItemComponentClass": {"MultiAmmo": ["A", "B"]},
        }
        assert get_ammo_code(data=data, data_service=data_service) is None

    def test_compatible_ammo_code_name(self, data_service: MagicMock) -> None:
        """CompatibleAmmoCodeName is used when present."""
        data = {
            "CodeName": "Weapon",
            "ItemComponentClass": {"CompatibleAmmoCodeName": "RifleAmmo"},
        }
        assert get_ammo_code(data=data, data_service=data_service) == "RifleAmmo"

    def test_projectile_class_explosive_code_name(self, data_service: MagicMock) -> None:
        """ProjectileClass.ExplosiveCodeName is used as a last resort."""
        data = {
            "CodeName": "Weapon",
            "ItemComponentClass": {"ProjectileClass": {"ExplosiveCodeName": "RPGExplosive"}},
        }
        assert get_ammo_code(data=data, data_service=data_service) == "RPGExplosive"

    def test_projectile_class_without_explosive_code_name(self, data_service: MagicMock) -> None:
        """A ProjectileClass dict with no ExplosiveCodeName resolves to None."""
        data = {
            "CodeName": "Weapon",
            "ItemComponentClass": {"ProjectileClass": {"Speed": 500}},
        }
        assert get_ammo_code(data=data, data_service=data_service) is None

    def test_no_matching_case_returns_none(self, data_service: MagicMock) -> None:
        """An ItemComponentClass matching none of the cases resolves to None."""
        data = {"CodeName": "Weapon", "ItemComponentClass": {"SomethingElse": True}}
        assert get_ammo_code(data=data, data_service=data_service) is None


class TestBuildDamageTypeResult:
    """Tests for build_damage_type_result."""

    def test_builds_object_path_from_bp_path(self, loc_service: MagicMock) -> None:
        """ObjectPath is derived from the blueprint path relative to Blueprints/."""
        result = build_damage_type_result(
            dt_data={}, bp_path="DamageTypes/BPKinetic.json", loc_service=loc_service
        )
        assert result["ObjectPath"]

    def test_copies_known_properties(self, loc_service: MagicMock) -> None:
        """Known scalar/flag properties are copied verbatim."""
        dt_data = {"Type": "Kinetic", "bCanWoundCharacter": True}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["Type"] == "Kinetic"
        assert result["bCanWoundCharacter"] is True

    def test_icon_simplified_to_resource_object(self, loc_service: MagicMock) -> None:
        """A dict Icon value is simplified to its ResourceObject field."""
        dt_data = {"Icon": {"ResourceObject": "/Game/Icons/Foo"}}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["Icon"] == "/Game/Icons/Foo"

    def test_display_name_guid_resolved(self, loc_service: MagicMock) -> None:
        """A GUID DisplayName is resolved via loc_service.get_with_fallback."""
        loc_service.is_guid.return_value = True
        dt_data = {"DisplayName": "guid-123"}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["DisplayName"] == "Resolved(guid-123)"

    def test_display_name_plain_text_used_as_is(self, loc_service: MagicMock) -> None:
        """A non-GUID DisplayName is used as-is."""
        dt_data = {"DisplayName": "Kinetic Damage"}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["DisplayName"] == "Kinetic Damage"

    def test_description_details_string_items(self, loc_service: MagicMock) -> None:
        """String DescriptionDetails entries are joined with newlines."""
        dt_data = {"DescriptionDetails": ["Line one", "Line two"]}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["DescriptionDetails"] == "Line one\nLine two"

    def test_description_details_guid_items_build_locales(self, loc_service: MagicMock) -> None:
        """GUID DescriptionDetails entries resolve text and populate per-language locales."""
        loc_service.is_guid.return_value = True
        loc_service.get_all_languages.return_value = {"en": "English text", "fr": "French text"}
        dt_data = {"DescriptionDetails": ["guid-1"]}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["DescriptionDetails"] == "Resolved(guid-1)"
        assert result["DescriptionDetailsLocales"] == {"en": "English text", "fr": "French text"}

    def test_description_details_nested_dict_text_with_guid(self, loc_service: MagicMock) -> None:
        """A nested {"Text": {"Text": ..., "Guid": ...}} item extracts text and tracks its GUID."""
        loc_service.is_guid.side_effect = lambda text: text == "guid-1"
        loc_service.get_all_languages.return_value = {"en": "English"}
        dt_data = {
            "DescriptionDetails": [{"Text": {"Text": "guid-1", "Guid": "guid-1"}}],
        }
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert "DescriptionDetails" in result

    def test_description_details_dict_item_plain_text(self, loc_service: MagicMock) -> None:
        """A dict item with a plain string Text field is used directly."""
        dt_data = {"DescriptionDetails": [{"Text": "Plain text"}]}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["DescriptionDetails"] == "Plain text"

    def test_description_details_skips_unrecognized_items(self, loc_service: MagicMock) -> None:
        """Items that are neither dict nor str are skipped."""
        dt_data: dict[str, Any] = {"DescriptionDetails": [123, ""]}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert "DescriptionDetails" not in result

    def test_description_details_generated_from_breaches_bunkers(
        self, loc_service: MagicMock
    ) -> None:
        """The bBreachesBunkers flag generates a DescriptionDetails line when none is set."""
        dt_data = {"bBreachesBunkers": True}
        result = build_damage_type_result(
            dt_data=dt_data, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert result["DescriptionDetails"] == "Always has a chance to breach bunkers"

    def test_no_description_details_when_nothing_applies(self, loc_service: MagicMock) -> None:
        """No DescriptionDetails key is added when there's nothing to generate."""
        result = build_damage_type_result(
            dt_data={}, bp_path="DamageTypes/BP.json", loc_service=loc_service
        )
        assert "DescriptionDetails" not in result


class TestResolveDamageType:
    """Tests for resolve_damage_type."""

    def test_no_damage_type_path_returns_none(
        self, data_service: MagicMock, loc_service: MagicMock
    ) -> None:
        """When the ammo data table has no DamageType reference, resolution returns None."""
        data_service.resolve_damage_type_import.return_value = None
        bp = MagicMock()
        result = resolve_damage_type(
            ammo_code="RifleAmmo",
            data_service=data_service,
            blueprint_parser=bp,
            loc_service=loc_service,
        )
        assert result is None

    def test_script_path_multi_segment_returns_type(
        self, data_service: MagicMock, loc_service: MagicMock
    ) -> None:
        """A /Script/ path with a package segment returns a short Type reference."""
        data_service.resolve_damage_type_import.return_value = "/Script/War/DamageType"
        bp = MagicMock()
        result = resolve_damage_type(
            ammo_code="RifleAmmo",
            data_service=data_service,
            blueprint_parser=bp,
            loc_service=loc_service,
        )
        assert result == {"Type": "/Script/War"}

    def test_game_path_missing_blueprint_returns_none(
        self, data_service: MagicMock, loc_service: MagicMock
    ) -> None:
        """When the resolved /Game/ blueprint cannot be loaded, resolution returns None."""
        data_service.resolve_damage_type_import.return_value = (
            "/Game/Blueprints/DamageTypes/BPKinetic"
        )
        bp = MagicMock()
        bp.extract_catalog_data.return_value = None
        result = resolve_damage_type(
            ammo_code="RifleAmmo",
            data_service=data_service,
            blueprint_parser=bp,
            loc_service=loc_service,
        )
        assert result is None

    def test_game_path_resolves_full_result(
        self, data_service: MagicMock, loc_service: MagicMock
    ) -> None:
        """A resolvable /Game/ path loads the blueprint and builds the full result."""
        data_service.resolve_damage_type_import.return_value = (
            "/Game/Blueprints/DamageTypes/BPKinetic_C/BPKinetic_C"
        )
        bp = MagicMock()
        bp.extract_catalog_data.return_value = {"Type": "Kinetic"}
        result = resolve_damage_type(
            ammo_code="RifleAmmo",
            data_service=data_service,
            blueprint_parser=bp,
            loc_service=loc_service,
        )
        assert result is not None
        assert result["Type"] == "Kinetic"
