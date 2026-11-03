"""Tests for CatalogService."""

import json
from pathlib import Path

import pytest

from foxhole_stockpiles.services.catalog_service import CatalogEntry, CatalogService


class TestCatalogEntry:
    """Tests for CatalogEntry model."""

    def test_catalog_entry_creation(self) -> None:
        """Test CatalogEntry can be created with required fields."""
        entry = CatalogEntry(code="ItemCode1", display_name="Item Name 1")

        assert entry.code == "ItemCode1"
        assert entry.display_name == "Item Name 1"


class TestCatalogService:
    """Tests for CatalogService."""

    def test_init_without_path(self) -> None:
        """Test service can be initialized without catalog path."""
        service = CatalogService(catalog_path=None)

        assert service._catalog_path is None
        assert service._loaded is False
        assert service._catalog == {}

    def test_init_with_path(self, tmp_path: Path) -> None:
        """Test service can be initialized with catalog path."""
        catalog_path = tmp_path / "catalog.json"
        service = CatalogService(catalog_path=catalog_path)

        assert service._catalog_path == catalog_path
        assert service._loaded is False

    def test_load_without_path_returns_codes(self) -> None:
        """Test that lookups return codes when no path is configured."""
        service = CatalogService(catalog_path=None)

        result = service.get_display_name("SomeCode")

        assert result == "SomeCode"
        assert service._loaded is True

    def test_load_with_missing_file(self, tmp_path: Path) -> None:
        """Test that missing catalog file is handled gracefully."""
        catalog_path = tmp_path / "nonexistent.json"
        service = CatalogService(catalog_path=catalog_path)

        result = service.get_display_name("SomeCode")

        assert result == "SomeCode"
        assert service._loaded is True

    def test_load_valid_catalog(self, tmp_path: Path) -> None:
        """Test loading a valid catalog file."""
        catalog_path = tmp_path / "catalog.json"
        catalog_data = [
            {"CodeName": "Item1", "DisplayName": "First Item"},
            {"CodeName": "Item2", "DisplayName": "Second Item"},
            {"CodeName": "Item3"},  # No display name
        ]
        catalog_path.write_text(json.dumps(catalog_data))

        service = CatalogService(catalog_path=catalog_path)

        assert service.get_display_name("Item1") == "First Item"
        assert service.get_display_name("Item2") == "Second Item"
        assert service.get_display_name("Item3") == "Item3"  # Falls back to code
        assert service.get_display_name("Unknown") == "Unknown"  # Not in catalog

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test handling of invalid JSON in catalog file."""
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("{ invalid json }")

        service = CatalogService(catalog_path=catalog_path)

        # Should not raise, should return code
        result = service.get_display_name("SomeCode")

        assert result == "SomeCode"
        assert service._loaded is True

    def test_load_only_once(self, tmp_path: Path) -> None:
        """Test that catalog is loaded only once (lazy loading)."""
        catalog_path = tmp_path / "catalog.json"
        catalog_data = [{"CodeName": "Item1", "DisplayName": "First Item"}]
        catalog_path.write_text(json.dumps(catalog_data))

        service = CatalogService(catalog_path=catalog_path)

        # First call loads
        assert service._loaded is False
        _ = service.get_display_name("Item1")
        assert service._loaded is True

        # Modify file (shouldn't affect loaded data)
        catalog_data[0]["DisplayName"] = "Modified"
        catalog_path.write_text(json.dumps(catalog_data))

        # Should still return original value
        assert service.get_display_name("Item1") == "First Item"

    def test_catalog_entries_without_codename_skipped(self, tmp_path: Path) -> None:
        """Test that entries without CodeName are skipped."""
        catalog_path = tmp_path / "catalog.json"
        catalog_data = [
            {"CodeName": "Item1", "DisplayName": "First Item"},
            {"DisplayName": "No Code Item"},  # No CodeName
            {"CodeName": "", "DisplayName": "Empty Code"},  # Empty CodeName
            {"CodeName": "Item2", "DisplayName": "Second Item"},
        ]
        catalog_path.write_text(json.dumps(catalog_data))

        service = CatalogService(catalog_path=catalog_path)

        # Only items with non-empty CodeName should be loaded
        assert service.get_display_name("Item1") == "First Item"
        assert service.get_display_name("Item2") == "Second Item"
        assert service.get_display_name("") == ""


class TestCategory:
    """The category an item is grouped under when it is displayed."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> CatalogService:
        """Build a service over a catalog with each kind of entry.

        Args:
            tmp_path (Path): Directory for the catalog.

        Returns:
            CatalogService: The service.
        """
        catalog = [
            {
                "CodeName": "RifleC",
                "DisplayName": "Rifle",
                "ItemCategory": "EItemCategory::SmallArms",
                "StockpileCategory": "Items",
            },
            {"CodeName": "TruckW", "DisplayName": "Truck", "StockpileCategory": "Vehicles"},
            {"CodeName": "Crane", "DisplayName": "Crane", "StockpileCategory": "Structures"},
            {"CodeName": "OldEntry", "DisplayName": "Old"},
        ]
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        return CatalogService(catalog_path=path)

    def test_item_uses_its_item_category_with_readable_words(self, service: CatalogService) -> None:
        """An Unreal enum value becomes a label."""
        assert service.get_category("RifleC") == "Small Arms"

    def test_vehicle_and_structure_use_their_stockpile_category(
        self, service: CatalogService
    ) -> None:
        """Vehicles and structures have no item category."""
        assert service.get_category("TruckW") == "Vehicles"
        assert service.get_category("Crane") == "Structures"

    def test_entry_without_any_category_has_none(self, service: CatalogService) -> None:
        """A catalog from an older build has no stockpile category."""
        assert service.get_category("OldEntry") is None

    def test_unknown_code_has_none(self, service: CatalogService) -> None:
        """A code missing from the catalog has no category."""
        assert service.get_category("Nope") is None


class TestNamesByLanguage:
    """The name of an item in another language."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> CatalogService:
        """Build a service with translated and untranslated names.

        Args:
            tmp_path (Path): The temporary directory.

        Returns:
            CatalogService: The service.
        """
        path = tmp_path / "catalog.json"
        entries = [
            {
                "CodeName": "Rifle",
                "DisplayName": "Rifle",
                "DisplayNameLocales": {"de": "Gewehr", "ru": "", "fr": 3},
            },
            {"CodeName": "Tank", "DisplayName": "Tank"},
        ]
        path.write_text(json.dumps(entries), encoding="utf-8")
        return CatalogService(catalog_path=path)

    def test_the_name_in_that_language(self, service: CatalogService) -> None:
        """When the catalog has it."""
        assert service.get_display_name("Rifle", language="de") == "Gewehr"

    def test_no_language_is_the_default_name(self, service: CatalogService) -> None:
        """As for everything that does not ask for one."""
        assert service.get_display_name("Rifle") == "Rifle"

    @pytest.mark.parametrize("language", ["es", "ru", "fr"])
    def test_a_missing_or_wrong_name_is_the_default_one(
        self, service: CatalogService, language: str
    ) -> None:
        """The game does not translate every item, nor has all the languages."""
        assert service.get_display_name("Rifle", language=language) == "Rifle"

    def test_an_item_without_translations(self, service: CatalogService) -> None:
        """Most vehicles have none."""
        assert service.get_display_name("Tank", language="de") == "Tank"

    def test_an_unknown_item_is_its_code(self, service: CatalogService) -> None:
        """In any language."""
        assert service.get_display_name("Nope", language="de") == "Nope"
