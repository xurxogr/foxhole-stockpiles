"""Tests for CatalogService."""

import json
from pathlib import Path

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

    def test_item_count(self, tmp_path: Path) -> None:
        """Test item_count returns correct count."""
        catalog_path = tmp_path / "catalog.json"
        catalog_data = [
            {"CodeName": "Item1", "DisplayName": "First Item"},
            {"CodeName": "Item2", "DisplayName": "Second Item"},
            {"CodeName": "Item3", "DisplayName": "Third Item"},
        ]
        catalog_path.write_text(json.dumps(catalog_data))

        service = CatalogService(catalog_path=catalog_path)

        assert service.item_count == 3

    def test_item_count_empty(self) -> None:
        """Test item_count returns 0 when no catalog."""
        service = CatalogService(catalog_path=None)

        assert service.item_count == 0

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
        assert service.item_count == 2
        assert service.get_display_name("Item1") == "First Item"
        assert service.get_display_name("Item2") == "Second Item"
