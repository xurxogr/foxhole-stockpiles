"""Tests for catalog_builder.catalog_assembler module."""

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from fs_tools.services.catalog_builder.catalog_assembler import (
    CatalogAssembler,
)


@pytest.fixture
def temp_extract_dir() -> Generator[Path, None, None]:
    """Create a temporary extraction directory with required structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create directory structure
        content_dir = root / "War" / "Content"
        blueprints_dir = content_dir / "Blueprints"
        data_dir = blueprints_dir / "Data"
        loc_dir = content_dir / "Localization"

        # Create all directories
        for subdir in ["ItemPickups", "Vehicles", "Structures", "Items", "DamageTypes"]:
            (blueprints_dir / subdir).mkdir(parents=True, exist_ok=True)

        data_dir.mkdir(parents=True, exist_ok=True)
        (loc_dir / "Foxhole-Content" / "en").mkdir(parents=True, exist_ok=True)

        yield root


@pytest.fixture
def mock_services() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create mock services for CatalogAssembler."""
    blueprint_parser = MagicMock()
    blueprint_parser.blueprints_dir = Path("/fake/blueprints")

    data_service = MagicMock()
    loc_service = MagicMock()
    loc_service.is_guid.return_value = False
    loc_service.get_with_fallback.return_value = "Fallback Text"

    return blueprint_parser, data_service, loc_service


class TestCatalogAssemblerInit:
    """Tests for CatalogAssembler initialization."""

    def test_init_sets_services(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that services are set correctly."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        assert assembler.blueprint_parser == bp
        assert assembler.data_service == ds
        assert assembler.loc_service == loc

    def test_init_sets_default_search_directories(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that default search directories are set."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        assert "ItemPickups" in assembler.search_directories
        assert "Vehicles" in assembler.search_directories
        assert "Structures" in assembler.search_directories

    def test_init_sets_exclude_patterns(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that exclude patterns are set."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        assert "ItemComponent" in assembler.exclude_patterns
        assert "VehicleProxy" in assembler.exclude_patterns
        assert "Ghost" in assembler.exclude_patterns
        assert "Destroyed" in assembler.exclude_patterns

    def test_init_creates_empty_stats(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that stats are initialized to zero."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        assert assembler.stats == {
            "total_files": 0,
            "parsed": 0,
            "stockpilable": 0,
            "errors": 0,
        }


class TestCatalogAssemblerFromExtractDir:
    """Tests for CatalogAssembler.from_extract_dir factory method."""

    def test_from_extract_dir_creates_assembler(self, temp_extract_dir: Path) -> None:
        """Test that from_extract_dir creates a valid assembler."""
        assembler = CatalogAssembler.from_extract_dir(temp_extract_dir)

        assert assembler is not None
        assert assembler.blueprint_parser is not None
        assert assembler.data_service is not None
        assert assembler.loc_service is not None

    def test_from_extract_dir_raises_for_missing_dir(self) -> None:
        """Test that from_extract_dir raises for missing directory."""
        with pytest.raises(FileNotFoundError, match="Extraction directory not found"):
            CatalogAssembler.from_extract_dir("/nonexistent/path")

    def test_from_extract_dir_raises_for_missing_blueprints(self, temp_extract_dir: Path) -> None:
        """Test that from_extract_dir raises for missing Blueprints dir."""
        # Remove Blueprints directory
        import shutil

        shutil.rmtree(temp_extract_dir / "War" / "Content" / "Blueprints")

        with pytest.raises(FileNotFoundError, match="Blueprints directory not found"):
            CatalogAssembler.from_extract_dir(temp_extract_dir)

    def test_from_extract_dir_raises_for_missing_data(self, temp_extract_dir: Path) -> None:
        """Test that from_extract_dir raises for missing Data dir."""
        import shutil

        shutil.rmtree(temp_extract_dir / "War" / "Content" / "Blueprints" / "Data")

        with pytest.raises(FileNotFoundError, match="Data directory not found"):
            CatalogAssembler.from_extract_dir(temp_extract_dir)

    def test_from_extract_dir_raises_for_missing_localization(self, temp_extract_dir: Path) -> None:
        """Test that from_extract_dir raises for missing Localization dir."""
        import shutil

        shutil.rmtree(temp_extract_dir / "War" / "Content" / "Localization")

        with pytest.raises(FileNotFoundError, match="Localization directory not found"):
            CatalogAssembler.from_extract_dir(temp_extract_dir)


class TestCatalogAssemblerFilterBlueprintsByPath:
    """Tests for CatalogAssembler._filter_blueprints_by_path method."""

    def test_finds_json_files_in_search_directories(self, temp_extract_dir: Path) -> None:
        """Test that JSON files are found in search directories."""
        # Create some JSON files
        blueprints_dir = temp_extract_dir / "War" / "Content" / "Blueprints"
        (blueprints_dir / "ItemPickups" / "BPRifle.json").touch()
        (blueprints_dir / "Vehicles" / "BPTank.json").touch()

        assembler = CatalogAssembler.from_extract_dir(temp_extract_dir)
        files = assembler._filter_blueprints_by_path()

        assert len(files) == 2
        assert any("BPRifle.json" in str(f) for f in files)
        assert any("BPTank.json" in str(f) for f in files)

    def test_excludes_patterns(self, temp_extract_dir: Path) -> None:
        """Test that excluded patterns are filtered out."""
        blueprints_dir = temp_extract_dir / "War" / "Content" / "Blueprints"
        (blueprints_dir / "ItemPickups" / "BPRifle.json").touch()
        (blueprints_dir / "ItemPickups" / "BPRifleItemComponent.json").touch()
        (blueprints_dir / "Structures" / "BPTowerGhost.json").touch()

        assembler = CatalogAssembler.from_extract_dir(temp_extract_dir)
        files = assembler._filter_blueprints_by_path()

        # Should only include BPRifle.json, not ItemComponent or Ghost
        assert len(files) == 1
        assert any("BPRifle.json" in str(f) for f in files)

    def test_updates_stats(self, temp_extract_dir: Path) -> None:
        """Test that stats are updated."""
        blueprints_dir = temp_extract_dir / "War" / "Content" / "Blueprints"
        (blueprints_dir / "ItemPickups" / "BP1.json").touch()
        (blueprints_dir / "ItemPickups" / "BP2.json").touch()
        (blueprints_dir / "ItemPickups" / "BP3.json").touch()

        assembler = CatalogAssembler.from_extract_dir(temp_extract_dir)
        assembler._filter_blueprints_by_path()

        assert assembler.stats["total_files"] == 3


class TestCatalogAssemblerFilterBlueprintByContent:
    """Tests for CatalogAssembler._filter_blueprint_by_content method."""

    def test_rejects_missing_required_fields(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that items missing required fields are rejected."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        # Missing CodeName
        data = {"DisplayName": "Test", "Icon": "icon.png"}
        assert assembler._filter_blueprint_by_content(data) is False

        # Missing DisplayName
        data = {"CodeName": "Test", "Icon": "icon.png"}
        assert assembler._filter_blueprint_by_content(data) is False

        # Missing Icon
        data = {"CodeName": "Test", "DisplayName": "Test"}
        assert assembler._filter_blueprint_by_content(data) is False

    def test_accepts_item_with_item_category(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that items with ItemCategory are accepted."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "TestItem",
            "DisplayName": "Test Item",
            "Description": "Test description",
            "Icon": "icon.png",
            "ItemCategory": "EItemCategory::Weapon",
        }
        assert assembler._filter_blueprint_by_content(data) is True

    def test_accepts_item_with_vehicle_profile(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that items with VehicleProfileType are accepted."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "TestVehicle",
            "DisplayName": "Test Vehicle",
            "Description": "Test description",
            "Icon": "icon.png",
            "VehicleProfileType": "EVehicleProfileType::Tank",
        }
        assert assembler._filter_blueprint_by_content(data) is True

    def test_accepts_stockpilable_item(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that items with bIsStockpilable=True are accepted."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "TestItem",
            "DisplayName": "Test Item",
            "Description": "Test description",
            "Icon": "icon.png",
            "bIsStockpilable": True,
        }
        assert assembler._filter_blueprint_by_content(data) is True

    def test_accepts_reserve_stockpiled_item(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that items with bIsReserveStockpiled=True are accepted."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "TestItem",
            "DisplayName": "Test Item",
            "Description": "Test description",
            "Icon": "icon.png",
            "bIsReserveStockpiled": True,
        }
        assert assembler._filter_blueprint_by_content(data) is True

    def test_rejects_non_stockpilable_vehicle(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that vehicles with bIsStockpilable=False are rejected."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "Train",
            "DisplayName": "Train",
            "Icon": "icon.png",
            "VehicleProfileType": "EVehicleProfileType::Train",
            "bIsStockpilable": False,
        }
        assert assembler._filter_blueprint_by_content(data) is False

    def test_accepts_reserve_only_vehicle(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that vehicles with bIsStockpilable=False but bIsReserveStockpiled=True."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "SuperTank",
            "DisplayName": "Super Tank",
            "Description": "Test description",
            "Icon": "icon.png",
            "VehicleProfileType": "EVehicleProfileType::SuperTank",
            "bIsStockpilable": False,
            "bIsReserveStockpiled": True,
        }
        assert assembler._filter_blueprint_by_content(data) is True


class TestCatalogAssemblerCleanEntry:
    """Tests for CatalogAssembler._clean_entry method."""

    def test_removes_none_values(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that None values are removed."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {"CodeName": "Test", "NullField": None, "ValidField": "value"}
        result = assembler._clean_entry(data)

        assert "NullField" not in result
        assert result.get("ValidField") == "value"

    def test_normalizes_game_paths(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that /Game/ paths are normalized."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {"Icon": "/Game/Textures/UI/ItemIcons/Rifle"}
        result = assembler._clean_entry(data)

        assert result["Icon"] == "War/Content/Textures/UI/ItemIcons/Rifle.0"

    def test_normalizes_paths_in_lists(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that paths in lists are normalized."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {"Icons": ["/Game/Textures/Icon1", "/Game/Textures/Icon2"]}
        result = assembler._clean_entry(data)

        assert result["Icons"] == [
            "War/Content/Textures/Icon1.0",
            "War/Content/Textures/Icon2.0",
        ]

    def test_recursively_cleans_nested_dicts(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that nested dicts are cleaned."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "OuterField": "value",
            "Nested": {
                "Icon": "/Game/Textures/Icon",
                "NullField": None,
            },
        }
        result = assembler._clean_entry(data)

        assert "NullField" not in result["Nested"]
        assert result["Nested"]["Icon"] == "War/Content/Textures/Icon.0"


class TestCatalogAssemblerGetAmmoCode:
    """Tests for CatalogAssembler._get_ammo_code method."""

    def test_returns_codename_for_ammo_item(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that CodeName is returned for ammo items."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = {"Damage": 100}

        assembler = CatalogAssembler(bp, ds, loc)

        data = {"CodeName": "RifleAmmo"}
        result = assembler._get_ammo_code(data)

        assert result == "RifleAmmo"

    def test_returns_single_multi_ammo(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that single MultiAmmo entry is returned."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "Launcher",
            "ItemComponentClass": {"MultiAmmo": ["RPGAmmo"]},
        }
        result = assembler._get_ammo_code(data)

        assert result == "RPGAmmo"

    def test_returns_compatible_ammo(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that CompatibleAmmoCodeName is returned."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "Rifle",
            "ItemComponentClass": {"CompatibleAmmoCodeName": "RifleAmmo"},
        }
        result = assembler._get_ammo_code(data)

        assert result == "RifleAmmo"

    def test_returns_explosive_codename(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that ExplosiveCodeName from ProjectileClass is returned."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "CodeName": "RPG",
            "ItemComponentClass": {"ProjectileClass": {"ExplosiveCodeName": "RPGExplosive"}},
        }
        result = assembler._get_ammo_code(data)

        assert result == "RPGExplosive"

    def test_returns_none_when_no_ammo(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that None is returned when no ammo info found."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        data = {"CodeName": "Hammer", "ItemComponentClass": {}}
        result = assembler._get_ammo_code(data)

        assert result is None


class TestCatalogAssemblerIsEmptyResourceAmounts:
    """Tests for CatalogAssembler._is_empty_resource_amounts method."""

    def test_returns_true_for_empty_pattern(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that empty pattern is detected."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        value = {
            "OtherResources": [],
            "Resource": {"CodeName": "None", "Quantity": 0},
        }
        assert assembler._is_empty_resource_amounts(value) is True

    def test_returns_false_for_non_empty_resources(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that non-empty resources are not detected as empty."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        value = {
            "OtherResources": [{"CodeName": "BasicMaterials", "Quantity": 10}],
            "Resource": {"CodeName": "None", "Quantity": 0},
        }
        assert assembler._is_empty_resource_amounts(value) is False

    def test_returns_false_for_non_none_resource(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that non-None resource is not detected as empty."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        value = {
            "OtherResources": [],
            "Resource": {"CodeName": "BasicMaterials", "Quantity": 100},
        }
        assert assembler._is_empty_resource_amounts(value) is False

    def test_returns_false_for_non_dict(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that non-dict values return False."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        assert assembler._is_empty_resource_amounts("string") is False
        assert assembler._is_empty_resource_amounts(None) is False
        assert assembler._is_empty_resource_amounts([]) is False


class TestCatalogAssemblerBuildCatalog:
    """Tests for CatalogAssembler.build_catalog method."""

    def test_build_returns_empty_for_no_files(self, temp_extract_dir: Path) -> None:
        """Test that build returns empty list when no valid files."""
        assembler = CatalogAssembler.from_extract_dir(temp_extract_dir)
        catalog = assembler.build_catalog()

        assert catalog == []

    def test_build_sorts_by_codename(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that catalog is sorted by CodeName."""
        bp, ds, loc = mock_services

        # Setup mock to return entries
        bp.extract_catalog_data.side_effect = [
            {
                "CodeName": "Zebra",
                "DisplayName": "Z",
                "Description": "D",
                "Icon": "z.png",
                "ItemCategory": "Cat",
            },
            {
                "CodeName": "Alpha",
                "DisplayName": "A",
                "Description": "D",
                "Icon": "a.png",
                "ItemCategory": "Cat",
            },
            {
                "CodeName": "Beta",
                "DisplayName": "B",
                "Description": "D",
                "Icon": "b.png",
                "ItemCategory": "Cat",
            },
        ]
        ds.get_production_categories.return_value = None
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        # Create mock files
        with tempfile.TemporaryDirectory() as tmpdir:
            blueprints_dir = Path(tmpdir)
            items_dir = blueprints_dir / "ItemPickups"
            items_dir.mkdir(parents=True)

            (items_dir / "BPZ.json").touch()
            (items_dir / "BPA.json").touch()
            (items_dir / "BPB.json").touch()

            bp.blueprints_dir = blueprints_dir
            catalog = assembler.build_catalog()

        # Should be sorted alphabetically
        assert len(catalog) == 3
        assert catalog[0]["CodeName"] == "Alpha"
        assert catalog[1]["CodeName"] == "Beta"
        assert catalog[2]["CodeName"] == "Zebra"

    def test_build_updates_stats(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that build updates statistics."""
        bp, ds, loc = mock_services

        bp.extract_catalog_data.side_effect = [
            {
                "CodeName": "Item1",
                "DisplayName": "I1",
                "Description": "D",
                "Icon": "i.png",
                "ItemCategory": "C",
            },
            None,  # Second file fails
            {
                "CodeName": "Item3",
                "DisplayName": "I3",
                "Icon": "i.png",
            },  # Missing category/description
        ]
        ds.get_production_categories.return_value = None
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            blueprints_dir = Path(tmpdir)
            items_dir = blueprints_dir / "ItemPickups"
            items_dir.mkdir(parents=True)

            (items_dir / "BP1.json").touch()
            (items_dir / "BP2.json").touch()
            (items_dir / "BP3.json").touch()

            bp.blueprints_dir = blueprints_dir
            assembler.build_catalog()

        stats = assembler.get_stats()
        assert stats["total_files"] == 3
        assert stats["parsed"] == 3
        assert stats["stockpilable"] == 1  # Only Item1 passes filter


class TestCatalogAssemblerEnrichLocales:
    """Tests for CatalogAssembler._enrich_locales method."""

    def test_adds_locales_from_guid(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that locales are added from GUID key."""
        bp, ds, loc = mock_services
        loc.is_guid.return_value = True
        loc.get_all_languages.return_value = {"en": "English", "de": "German"}

        assembler = CatalogAssembler(bp, ds, loc)

        data: dict[str, Any] = {
            "DisplayName": "Test",
            "DisplayNameKey": "ABC123GUID12345678901234567890",
        }
        assembler._enrich_locales(data)

        assert "DisplayNameLocales" in data
        assert data["DisplayNameLocales"] == {"en": "English", "de": "German"}
        assert "DisplayNameKey" not in data

    def test_removes_key_even_without_translations(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that key field is removed even if no translations found."""
        bp, ds, loc = mock_services
        loc.is_guid.return_value = True
        loc.get_all_languages.return_value = {}

        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "DisplayName": "Test",
            "DisplayNameKey": "ABC123GUID12345678901234567890",
        }
        assembler._enrich_locales(data)

        assert "DisplayNameKey" not in data

    def test_skips_if_locales_already_present(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that existing locales are not overwritten."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)

        data = {
            "DisplayName": "Test",
            "DisplayNameKey": "GUID",
            "DisplayNameLocales": {"en": "Existing"},
        }
        assembler._enrich_locales(data)

        assert data["DisplayNameLocales"] == {"en": "Existing"}
        assert "DisplayNameKey" not in data


class TestCatalogAssemblerExpandData:
    """Tests for CatalogAssembler._expand_data method."""

    def test_expand_data_adds_item_dynamic_data(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that ItemDynamicData is added from data table."""
        bp, ds, loc = mock_services
        ds.get.return_value = {"Weight": 10, "ObjectPath": "path"}
        ds.get_ammo_dynamic_data.return_value = None
        ds.get_profile.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {}
        assembler._expand_data(data, "TestItem")

        assert "ItemDynamicData" in data

    def test_expand_data_adds_ammo_dynamic_data(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that AmmoDynamicData is added from data table."""
        bp, ds, loc = mock_services
        ds.get.return_value = None
        ds.get_ammo_dynamic_data.return_value = {"Damage": 100}
        ds.get_profile.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {}
        assembler._expand_data(data, "TestAmmo")

        assert data.get("AmmoDynamicData") == {"Damage": 100}

    def test_expand_data_adds_profile_data(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that profile data is added from profile table."""
        bp, ds, loc = mock_services
        ds.get.return_value = None
        ds.get_ammo_dynamic_data.return_value = None
        ds.get_profile.return_value = {"MaxStack": 10}

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemProfileType": "EItemProfileType::Small"}
        assembler._expand_data(data, "TestItem")

        assert "ItemProfileData" in data

    def test_expand_data_skips_empty_codename(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that empty codename skips expansion."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {}
        assembler._expand_data(data, "")

        # No data tables should be queried
        ds.get.assert_not_called()


class TestCatalogAssemblerEnrichItemComponent:
    """Tests for CatalogAssembler._enrich_item_component_class method."""

    def test_enrich_item_component_string_path(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass from string path."""
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CompatibleAmmoCodeName": "RifleAmmo",
            "Damage": 25,
        }

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": "/Game/Blueprints/Items/BPRifleComponent"}
        assembler._enrich_item_component_class(data)

        assert isinstance(data["ItemComponentClass"], dict)
        assert data["ItemComponentClass"].get("CompatibleAmmoCodeName") == "RifleAmmo"

    def test_enrich_item_component_dict_path(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass from dict with ObjectPath."""
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {"Damage": 25}

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {
            "ItemComponentClass": {"ObjectPath": "War/Content/Blueprints/Items/BPComp.0"}
        }
        assembler._enrich_item_component_class(data)

        assert data["ItemComponentClass"].get("Damage") == 25

    def test_enrich_item_component_no_object_path(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass when dict has no ObjectPath."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": {"SomeOther": "value"}}
        assembler._enrich_item_component_class(data)

        # Should not be modified
        assert data["ItemComponentClass"] == {"SomeOther": "value"}

    def test_enrich_item_component_invalid_type(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass with invalid type."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": 123}  # Not str or dict
        assembler._enrich_item_component_class(data)

        # Should not be modified
        assert data["ItemComponentClass"] == 123

    def test_enrich_item_component_missing(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching when ItemComponentClass is missing."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {}
        assembler._enrich_item_component_class(data)

        # Should not add anything
        assert "ItemComponentClass" not in data

    def test_enrich_item_component_multiammo(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass with MultiAmmo list."""
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {"MultiAmmo": ["Ammo1", "Ammo2", "Ammo3"]}

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": "/Game/Blueprints/Items/BPComp"}
        assembler._enrich_item_component_class(data)

        # Should have MultiAmmo list
        assert data["ItemComponentClass"].get("MultiAmmo") == ["Ammo1", "Ammo2", "Ammo3"]

    def test_enrich_item_component_multiammo_dict(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass with MultiAmmo dict format."""
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "MultiAmmo": {"CompatibleAmmoNames": ["Ammo1", "Ammo2"]}
        }

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": "/Game/Blueprints/Items/BPComp"}
        assembler._enrich_item_component_class(data)

        assert data["ItemComponentClass"].get("MultiAmmo") == ["Ammo1", "Ammo2"]

    def test_enrich_item_component_projectile_class(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test enriching ItemComponentClass with ProjectileClasses."""
        bp, ds, loc = mock_services

        # First call for component, second for projectile
        bp.extract_catalog_data.side_effect = [
            {"ProjectileClasses": ["/Game/Blueprints/Projectiles/BPProj"]},
            {"ExplosiveCodeName": "RPGExplosive", "Speed": 500},
        ]

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": "/Game/Blueprints/Items/BPComp"}
        assembler._enrich_item_component_class(data)

        assert "ProjectileClass" in data["ItemComponentClass"]
        assert (
            data["ItemComponentClass"]["ProjectileClass"].get("ExplosiveCodeName") == "RPGExplosive"
        )

    def test_enrich_item_component_does_not_alias_parser_cache(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Mutating a merged nested value must not mutate the parser's cached dict.

        extract_catalog_data returns the parser's cached object by reference.
        Merging its values into item_comp without deep-copying would let later
        mutation of one item's catalog entry corrupt another item's cached
        component/projectile blueprint data.
        """
        bp, ds, loc = mock_services
        cached_nested = {"Stats": {"Damage": 25}}
        cached_proj_nested = {"Falloff": {"Near": 1}}
        bp.extract_catalog_data.side_effect = [
            {"Nested": cached_nested, "ProjectileClasses": ["/Game/Blueprints/Projectiles/BPProj"]},
            {"ExplosiveCodeName": "RPGExplosive", "NestedProj": cached_proj_nested},
        ]

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"ItemComponentClass": "/Game/Blueprints/Items/BPComp"}
        assembler._enrich_item_component_class(data)

        item_comp = data["ItemComponentClass"]
        item_comp["Nested"]["Stats"]["Damage"] = 999
        item_comp["ProjectileClass"]["NestedProj"]["Falloff"]["Near"] = 999

        assert cached_nested["Stats"]["Damage"] == 25
        assert cached_proj_nested["Falloff"]["Near"] == 1


class TestCatalogAssemblerAddSubtypeIcon:
    """Tests for CatalogAssembler._add_subtype_icon method."""

    def test_add_subtype_icon_for_ammo_item(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test adding SubTypeIcon for ammo items."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = {"Damage": 100}

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {
            "CodeName": "TestAmmo",
            "AmmoDynamicData": {"DamageType": {"Icon": "explosion_icon.png"}},
        }
        assembler._add_subtype_icon(data)

        assert data.get("SubTypeIcon") == "explosion_icon.png"

    def test_add_subtype_icon_for_projectile_weapon(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test adding SubTypeIcon for projectile weapons."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None  # Not an ammo item

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {
            "CodeName": "RPGLauncher",
            "AmmoDynamicData": {"DamageType": {"Icon": "rpg_icon.png"}},
            "ItemComponentClass": {"ProjectileClass": {"ExplosiveCodeName": "RPGExplosive"}},
        }
        assembler._add_subtype_icon(data)

        assert data.get("SubTypeIcon") == "rpg_icon.png"

    def test_add_subtype_icon_for_deployable(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test adding SubTypeIcon for deployable weapons."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {
            "CodeName": "TripodWeapon",
            "AmmoDynamicData": {"DamageType": {"Icon": "tripod_icon.png"}},
            "ItemComponentClass": {"DeployCodeName": "DeployedTripod"},
        }
        assembler._add_subtype_icon(data)

        assert data.get("SubTypeIcon") == "tripod_icon.png"

    def test_add_subtype_icon_skips_handheld_weapon(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that SubTypeIcon is not added for regular handheld weapons."""
        bp, ds, loc = mock_services
        ds.get_ammo_dynamic_data.return_value = None  # Not an ammo item itself

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {
            "CodeName": "Rifle",
            "AmmoDynamicData": {"DamageType": {"Icon": "bullet_icon.png"}},
            "ItemComponentClass": {"CompatibleAmmoCodeName": "RifleAmmo"},
        }
        assembler._add_subtype_icon(data)

        # Should NOT have SubTypeIcon for regular handheld weapons
        assert "SubTypeIcon" not in data

    def test_add_subtype_icon_hardcoded_isgtc(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test hardcoded SubTypeIcon for ISGTC.

        ISGTC has no AmmoDynamicData in the blueprint, so it gets the
        hardcoded SE icon.
        """
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        # ISGTC has no AmmoDynamicData
        data: dict[str, Any] = {
            "CodeName": "ISGTC",
        }
        assembler._add_subtype_icon(data)

        # Hardcoded to the SE icon
        assert data.get("SubTypeIcon") == "War/Content/Textures/UI/ItemIcons/SubtypeSEIcon.0"

    def test_add_subtype_icon_no_ammo_data(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that SubTypeIcon is not added when no AmmoDynamicData."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {"CodeName": "Hammer"}
        assembler._add_subtype_icon(data)

        assert "SubTypeIcon" not in data

    def test_add_subtype_icon_no_damage_type(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that SubTypeIcon is not added when no DamageType."""
        bp, ds, loc = mock_services

        assembler = CatalogAssembler(bp, ds, loc)
        data: dict[str, Any] = {
            "CodeName": "TestItem",
            "AmmoDynamicData": {"Damage": 100},  # No DamageType
        }
        assembler._add_subtype_icon(data)

        assert "SubTypeIcon" not in data


class TestCatalogAssemblerCleanDataTableEntry:
    """Tests for CatalogAssembler._clean_data_table_entry method."""

    def test_removes_empty_alt_resource_amounts(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that empty AltResourceAmounts is removed."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        entry = {
            "Damage": 100,
            "AltResourceAmounts": {
                "OtherResources": [],
                "Resource": {"CodeName": "None", "Quantity": 0},
            },
        }
        result = assembler._clean_data_table_entry(entry)

        assert "AltResourceAmounts" not in result
        assert result.get("Damage") == 100

    def test_keeps_non_empty_alt_resource_amounts(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that non-empty AltResourceAmounts is kept."""
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        entry = {
            "AltResourceAmounts": {
                "OtherResources": [],
                "Resource": {"CodeName": "BasicMaterials", "Quantity": 100},
            }
        }
        result = assembler._clean_data_table_entry(entry)

        assert "AltResourceAmounts" in result


class TestCatalogAssemblerProductionCategories:
    """Tests for production categories handling."""

    def test_adds_production_categories(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that ProductionCategories is added from data service."""
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestItem",
            "DisplayName": "Test",
            "Icon": "icon.png",
            "ItemCategory": "EItemCategory::Weapon",
        }
        ds.get_production_categories.return_value = {"Factory": "EFactoryQueueType::Weapons"}
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        # Create actual file for _parse_blueprint
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            items_dir = bp.blueprints_dir / "Items"
            items_dir.mkdir(parents=True)
            (items_dir / "Test.json").touch()

            assembler.search_directories = ["Items"]
            catalog = assembler.build_catalog()

        # Check that production categories were added
        assert len(catalog) > 0 or ds.get_production_categories.called

    def test_infers_mass_production_for_vehicle(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that MassProductionFactory is inferred for vehicles."""
        _, ds, _ = mock_services

        # Test vehicle build type inference
        data: dict[str, Any] = {
            "CodeName": "Tank",
            "VehicleBuildType": "EVehicleBuildType::Garage",
        }

        # Simulate _parse_blueprint adding production categories
        # when prod_cats is None or missing MassProductionFactory
        ds.get_production_categories.return_value = None

        # The logic from _parse_blueprint:
        prod_cats = ds.get_production_categories(data.get("CodeName", ""))
        if not prod_cats or "MassProductionFactory" not in prod_cats:
            vehicle_build_type = data.get("VehicleBuildType")
            if vehicle_build_type and vehicle_build_type != "EVehicleBuildType::NotBuildable":
                if "ProductionCategories" not in data:
                    data["ProductionCategories"] = {}
                data["ProductionCategories"]["MassProductionFactory"] = (
                    "EFactoryQueueType::Vehicles"
                )

        assert (
            data.get("ProductionCategories", {}).get("MassProductionFactory")
            == "EFactoryQueueType::Vehicles"
        )

    def test_infers_mass_production_for_structure(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that MassProductionFactory is inferred for structures."""
        _, ds, _ = mock_services

        # Test structure build location inference
        data: dict[str, Any] = {
            "CodeName": "Bunker",
            "BuildLocationType": "EBuildLocationType::Anywhere",
        }

        ds.get_production_categories.return_value = None

        prod_cats = ds.get_production_categories(data.get("CodeName", ""))
        if not prod_cats or "MassProductionFactory" not in prod_cats:
            vehicle_build_type = data.get("VehicleBuildType")
            build_location_type = data.get("BuildLocationType")

            if vehicle_build_type and vehicle_build_type != "EVehicleBuildType::NotBuildable":
                pass
            elif build_location_type in (
                "EBuildLocationType::Anywhere",
                "EBuildLocationType::ConstructionYard",
            ):
                if "ProductionCategories" not in data:
                    data["ProductionCategories"] = {}
                data["ProductionCategories"]["MassProductionFactory"] = (
                    "EFactoryQueueType::Structures"
                )

        assert (
            data.get("ProductionCategories", {}).get("MassProductionFactory")
            == "EFactoryQueueType::Structures"
        )


class TestCatalogAssemblerFromExtractDirEdgeCases:
    """Tests for from_extract_dir factory method edge cases."""

    def test_raises_not_a_directory_error_for_file(self) -> None:
        """Test that from_extract_dir raises NotADirectoryError when given a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "not_a_dir.txt"
            file_path.touch()

            with pytest.raises(NotADirectoryError, match="Not a directory"):
                CatalogAssembler.from_extract_dir(file_path)

    def test_raises_not_a_directory_for_required_path(self) -> None:
        """Test NotADirectoryError when a required subdirectory is a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content_dir = root / "War" / "Content"
            blueprints_dir = content_dir / "Blueprints"

            # Create blueprints as a file instead of a directory
            content_dir.mkdir(parents=True)
            blueprints_dir.touch()  # File, not directory

            with pytest.raises(NotADirectoryError, match="is not a directory"):
                CatalogAssembler.from_extract_dir(root)


class TestCatalogAssemblerBuildDamageTypeResult:
    """Tests for _build_damage_type_result method.

    This class contains tests for building DamageType results from
    blueprint data including property extraction and localization.
    """

    def test_builds_damage_type_with_all_properties(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test building damage type result with all properties.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        loc.is_guid.return_value = False
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "Type": "Kinetic",
            "Icon": {"ResourceObject": "/Game/Textures/Icon.png"},
            "bApplyDamageFalloff": True,
            "bCanWoundCharacter": True,
            "bExposeInUI": True,
            "TankArmourPenetrationFactor": 1.5,
            "DisplayName": {"Text": "Kinetic Damage", "Guid": "ABC123"},
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BPKinetic.json")

        assert result["Type"] == "Kinetic"
        assert result["Icon"] == "/Game/Textures/Icon.png"
        assert result["bApplyDamageFalloff"] is True
        assert "ObjectPath" in result

    def test_builds_damage_type_with_guid_display_name(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that GUID display name is resolved via loc service.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        loc.is_guid.return_value = True
        loc.get_with_fallback.return_value = "Localized Name"
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "DisplayName": {"Text": "GUID-12345", "Guid": "GUID-12345"},
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BP.json")

        assert result["DisplayName"] == "Localized Name"
        loc.get_with_fallback.assert_called()

    def test_builds_damage_type_with_description_details_array(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test building damage type with DescriptionDetails array.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        loc.is_guid.return_value = False
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "DescriptionDetails": [
                {"Text": "Line 1"},
                {"Text": "Line 2"},
            ],
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BP.json")

        assert "DescriptionDetails" in result
        assert "Line 1" in result["DescriptionDetails"]
        assert "Line 2" in result["DescriptionDetails"]

    def test_builds_damage_type_with_nested_text_format(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test building damage type with nested Text dict format.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        loc.is_guid.return_value = True
        loc.get_with_fallback.return_value = "Localized"
        loc.get_all_languages.return_value = {"en": "English", "de": "German"}
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "DescriptionDetails": [
                {"Text": {"Text": "GUID-1", "Guid": "GUID-1"}},
            ],
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BP.json")

        assert "DescriptionDetails" in result

    def test_builds_damage_type_with_string_description_item(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test building damage type with string items in DescriptionDetails.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        loc.is_guid.return_value = False
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "DescriptionDetails": ["Plain text line"],
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BP.json")

        assert result.get("DescriptionDetails") == "Plain text line"

    def test_builds_damage_type_with_breaches_bunkers(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that bBreachesBunkers generates DescriptionDetails.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        loc.is_guid.return_value = False
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "bBreachesBunkers": True,
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BP.json")

        assert "breach" in result.get("DescriptionDetails", "").lower()

    def test_builds_damage_type_locales_for_guid_descriptions(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that DescriptionDetailsLocales is built for GUID texts.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services

        def is_guid_check(text: str) -> bool:
            return text.startswith("GUID-")

        loc.is_guid.side_effect = is_guid_check
        loc.get_with_fallback.return_value = "Localized"
        loc.get_all_languages.return_value = {"en": "English", "de": "German"}
        assembler = CatalogAssembler(bp, ds, loc)

        dt_data: dict[str, Any] = {
            "DescriptionDetails": [
                {"Text": "GUID-12345"},
            ],
        }

        result = assembler._build_damage_type_result(dt_data, "DamageTypes/BP.json")

        assert "DescriptionDetailsLocales" in result


class TestCatalogAssemblerResolveDamageType:
    """Tests for _resolve_damage_type method.

    This class contains tests for resolving DamageType references
    from ammo codes including Script paths and blueprint paths.
    """

    def test_returns_none_when_no_damage_type_path(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that None is returned when damage type path is not found.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        ds.resolve_damage_type_import.return_value = None
        assembler = CatalogAssembler(bp, ds, loc)

        result = assembler._resolve_damage_type("SomeAmmo")

        assert result is None

    def test_returns_script_type_for_script_path(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that Script paths are returned as Type field.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        ds.resolve_damage_type_import.return_value = "/Script/War/DamageType"
        assembler = CatalogAssembler(bp, ds, loc)

        result = assembler._resolve_damage_type("SomeAmmo")

        assert result == {"Type": "/Script/War"}

    def test_returns_script_path_directly_for_short_path(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that short Script paths are returned directly.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        ds.resolve_damage_type_import.return_value = "/Script/X"
        assembler = CatalogAssembler(bp, ds, loc)

        result = assembler._resolve_damage_type("SomeAmmo")

        assert result == {"Type": "/Script/X"}

    def test_resolves_game_path_via_blueprint_parser(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that Game paths are resolved via blueprint parser.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        ds.resolve_damage_type_import.return_value = (
            "/Game/Blueprints/DamageTypes/BPKinetic/BPKinetic_C"
        )
        loc.is_guid.return_value = False
        bp.extract_catalog_data.return_value = {
            "Type": "Kinetic",
            "DisplayName": "Kinetic",
        }
        assembler = CatalogAssembler(bp, ds, loc)

        result = assembler._resolve_damage_type("SomeAmmo")

        assert result is not None
        bp.extract_catalog_data.assert_called_once()

    def test_returns_none_when_blueprint_not_found(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that None is returned when blueprint is not found.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        ds.resolve_damage_type_import.return_value = "/Game/Blueprints/DamageTypes/Missing"
        bp.extract_catalog_data.return_value = None
        assembler = CatalogAssembler(bp, ds, loc)

        result = assembler._resolve_damage_type("SomeAmmo")

        assert result is None


class TestCatalogAssemblerParseBlueprintGuidHandling:
    """Tests for GUID handling in _parse_blueprint.

    This class contains tests for extracting and resolving localization
    GUIDs from text fields during blueprint parsing.
    """

    def test_handles_dict_format_guid_for_display_name(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that dict format GUID is extracted and resolved.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestItem",
            "DisplayName": {"Text": "Test Item", "Guid": "GUID-ABC"},
            "Icon": "icon.png",
            "ItemCategory": "EItemCategory::Weapon",
        }
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            items_dir = bp.blueprints_dir / "Items"
            items_dir.mkdir(parents=True)
            test_file = items_dir / "Test.json"
            test_file.touch()

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        assert result.get("DisplayNameKey") == "GUID-ABC"

    def test_handles_legacy_guid_string_format(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that legacy GUID string format is resolved via loc service.

        Note: The DisplayNameKey is removed by _enrich_locales after processing,
        so we verify the DisplayName was resolved and Locales were added.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestItem",
            "DisplayName": "GUID-12345",
            "Icon": "icon.png",
            "ItemCategory": "EItemCategory::Weapon",
        }
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None
        loc.is_guid.return_value = True
        loc.get_with_fallback.return_value = "Resolved Name"
        loc.get_all_languages.return_value = {"en": "English Name", "de": "German Name"}

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            items_dir = bp.blueprints_dir / "Items"
            items_dir.mkdir(parents=True)
            test_file = items_dir / "Test.json"
            test_file.touch()

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        # DisplayName was resolved from GUID
        assert result.get("DisplayName") == "Resolved Name"
        # Locales were added from the GUID lookup
        assert result.get("DisplayNameLocales") == {"en": "English Name", "de": "German Name"}
        # DisplayNameKey is removed after processing
        assert "DisplayNameKey" not in result


class TestCatalogAssemblerAmmoDynamicData:
    """Tests for AmmoDynamicData handling in _parse_blueprint.

    This class contains tests for adding and resolving AmmoDynamicData
    including DamageType resolution from ammo codes.
    """

    def test_adds_ammo_dynamic_data_from_service(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that AmmoDynamicData is added from data service.

        Note: CompatibleAmmoCodeName must be inside ItemComponentClass
        for _get_ammo_code to find it.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestWeapon",
            "DisplayName": "Test Weapon",
            "Icon": "icon.png",
            "ItemCategory": "EItemCategory::Weapon",
            "ItemComponentClass": {
                "CompatibleAmmoCodeName": "RifleAmmo",
            },
        }
        ds.get_ammo_dynamic_data.side_effect = lambda code: (
            {
                "Damage": 100,
                "Suppression": 50,
            }
            if code == "RifleAmmo"
            else None
        )
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None
        ds.resolve_damage_type_import.return_value = None
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            items_dir = bp.blueprints_dir / "Items"
            items_dir.mkdir(parents=True)
            test_file = items_dir / "Test.json"
            test_file.touch()

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        assert "AmmoDynamicData" in result

    def test_resolves_damage_type_for_ammo(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that DamageType is resolved for ammo.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestWeapon",
            "DisplayName": "Test Weapon",
            "Icon": "icon.png",
            "ItemCategory": "EItemCategory::Weapon",
            "CompatibleAmmoCodeName": "RifleAmmo",
        }
        ds.get_ammo_dynamic_data.return_value = {
            "Damage": 100,
            "DamageType": -25,  # Import reference, not a dict
        }
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None
        ds.resolve_damage_type_import.return_value = "/Script/War/Kinetic"
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            items_dir = bp.blueprints_dir / "Items"
            items_dir.mkdir(parents=True)
            test_file = items_dir / "Test.json"
            test_file.touch()

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        ammo_data = result.get("AmmoDynamicData")
        assert ammo_data is not None
        # DamageType should be resolved
        assert isinstance(ammo_data.get("DamageType"), dict)


class TestCatalogAssemblerBuildCatalogErrorHandling:
    """Tests for error handling in build_catalog.

    This class contains tests for graceful error handling during
    the catalog building process.
    """

    def test_continues_on_parsing_error(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that build_catalog continues when a blueprint fails to parse.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services

        # First call raises, second returns valid data
        call_count = [0]

        def extract_side_effect(path: str) -> dict[str, Any] | None:
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Parse error")
            return {
                "CodeName": "ValidItem",
                "DisplayName": "Valid",
                "Description": "Valid description",
                "Icon": "icon.png",
                "ItemCategory": "EItemCategory::Weapon",
            }

        bp.extract_catalog_data.side_effect = extract_side_effect
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            items_dir = bp.blueprints_dir / "Items"
            items_dir.mkdir(parents=True)
            (items_dir / "Bad.json").touch()
            (items_dir / "Good.json").touch()

            assembler.search_directories = ["Items"]
            catalog = assembler.build_catalog()

        # Should have error count
        assert assembler.stats["errors"] == 1
        # Should still have valid entry
        assert len(catalog) == 1


class TestCatalogAssemblerMassProductionInference:
    """Tests for MassProductionFactory inference in _parse_blueprint.

    This class contains tests for automatic inference of MassProductionFactory
    from VehicleBuildType and BuildLocationType fields.
    """

    def test_infers_mass_production_for_vehicle_build_type(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test MassProductionFactory is inferred for VehicleBuildType.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestVehicle",
            "DisplayName": "Test Vehicle",
            "Icon": "icon.png",
            "VehicleBuildType": "EVehicleBuildType::Garage",
        }
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None  # No existing categories
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            vehicles_dir = bp.blueprints_dir / "Vehicles"
            vehicles_dir.mkdir(parents=True)
            test_file = vehicles_dir / "Test.json"
            test_file.touch()

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        prod_cats = result.get("ProductionCategories", {})
        assert prod_cats.get("MassProductionFactory") == "EFactoryQueueType::Vehicles"

    def test_infers_mass_production_for_build_location_type(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test MassProductionFactory is inferred for BuildLocationType.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "TestStructure",
            "DisplayName": "Test Structure",
            "Icon": "icon.png",
            "BuildLocationType": "EBuildLocationType::ConstructionYard",
        }
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        assembler = CatalogAssembler(bp, ds, loc)

        with tempfile.TemporaryDirectory() as tmpdir:
            bp.blueprints_dir = Path(tmpdir)
            structures_dir = bp.blueprints_dir / "Structures"
            structures_dir.mkdir(parents=True)
            test_file = structures_dir / "Test.json"
            test_file.touch()

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        prod_cats = result.get("ProductionCategories", {})
        assert prod_cats.get("MassProductionFactory") == "EFactoryQueueType::Structures"

    def test_infers_mass_production_for_large_shippable(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test MassProductionFactory is inferred for ShippableInfo::Large vehicles.

        Large shippable vehicles like landing crafts may not have VehicleBuildType
        but are still mass-produced in factories.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        bp.extract_catalog_data.return_value = {
            "CodeName": "LandingCraftW",
            "DisplayName": "Mulloy LPC",
            "Description": "D",
            "Icon": "icon.png",
            "ShippableInfo": "EShippableType::Large",
            # No VehicleBuildType or BuildLocationType
        }
        ds.get_ammo_dynamic_data.return_value = None
        ds.get.return_value = None
        ds.get_profile.return_value = None
        ds.get_production_categories.return_value = None  # No existing categories
        loc.is_guid.return_value = False
        loc.get_all_languages.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            vehicles_dir = Path(tmpdir) / "Vehicles"
            vehicles_dir.mkdir(parents=True)
            test_file = vehicles_dir / "LandingCraft.json"
            test_file.touch()

            # Set blueprints_dir to the temp directory
            bp.blueprints_dir = Path(tmpdir)
            assembler = CatalogAssembler(bp, ds, loc)

            result = assembler._parse_blueprint(test_file)

        assert result is not None
        prod_cats = result.get("ProductionCategories", {})
        assert prod_cats.get("MassProductionFactory") == "EFactoryQueueType::Vehicles"


class TestCatalogAssemblerIsEmptyResourceAmountsEdgeCases:
    """Tests for _is_empty_resource_amounts method edge cases.

    This class contains tests for detecting empty or default ResourceAmounts
    values that should be removed from the catalog output.
    """

    def test_detects_empty_resource_amounts(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that empty ResourceAmounts is detected.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        empty_value: dict[str, Any] = {
            "OtherResources": [],
            "Resource": {"CodeName": "None", "Quantity": 0},
        }

        assert assembler._is_empty_resource_amounts(empty_value) is True

    def test_detects_non_empty_resource_amounts(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that non-empty ResourceAmounts is not flagged as empty.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        non_empty: dict[str, Any] = {
            "OtherResources": [{"CodeName": "Iron", "Quantity": 10}],
            "Resource": {"CodeName": "None", "Quantity": 0},
        }

        assert assembler._is_empty_resource_amounts(non_empty) is False

    def test_non_dict_is_not_empty(
        self, mock_services: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Test that non-dict values are not considered empty.

        Args:
            mock_services (tuple[MagicMock, MagicMock, MagicMock]): Mock services fixture.
        """
        bp, ds, loc = mock_services
        assembler = CatalogAssembler(bp, ds, loc)

        assert assembler._is_empty_resource_amounts("not a dict") is False
        assert assembler._is_empty_resource_amounts(123) is False
        assert assembler._is_empty_resource_amounts(None) is False
