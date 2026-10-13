"""Tests for Stockpile model.

This module contains comprehensive tests for the Stockpile model,
including business logic, serialization, and application-specific functionality.
"""

from datetime import datetime

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class TestStockpile:
    """Test cases for Stockpile model.

    This class contains tests for Stockpile business logic and serialization.
    """

    def test_stockpile_serialization(self) -> None:
        """Test stockpile serialization for API responses."""
        custom_time = datetime(2024, 1, 4, 9, 0, 0)
        items = [StockpileItem(code="BasicMaterialsIcon", quantity=100, confidence=0.95)]

        stockpile = Stockpile(
            name="Test Base",
            type=StockpileType.SEAPORT,
            items=items,
            timestamp=custom_time,
            shard="TEST",
        )

        json_data = stockpile.model_dump()

        # Verify serialization produces expected API format
        assert json_data["type"] == "Seaport"
        assert json_data["timestamp"] == "2024-01-04T09:00:00"
        assert len(json_data["items"]) == 1
        assert json_data["items"][0]["code"] == "BasicMaterialsIcon"

    def test_stockpile_with_multiple_items(self) -> None:
        """Test stockpile with multiple items for business logic."""
        items = [
            StockpileItem(code="BasicMaterialsIcon", quantity=100),
            StockpileItem(code="PetrolIcon", quantity=50),
            StockpileItem(code="DieselIcon", quantity=75),
        ]

        stockpile = Stockpile(name="Multi-Item Base", items=items)

        assert len(stockpile.items) == 3
        assert stockpile.items[0].code == "BasicMaterialsIcon"
        assert stockpile.items[1].code == "PetrolIcon"
        assert stockpile.items[2].code == "DieselIcon"

    def test_stockpile_with_errors(self) -> None:
        """Test stockpile error tracking functionality."""
        errors = [
            "No icon detected in group 1, index 67 with confidence 0.75",
            "Template matching failed for unknown icon",
            "OCR failed to read quantity in position (100, 200)",
        ]

        stockpile = Stockpile(name="Error Test", errors=errors)

        assert len(stockpile.errors) == 3
        assert "No icon detected" in stockpile.errors[0]
        assert "Template matching failed" in stockpile.errors[1]
        assert "OCR failed" in stockpile.errors[2]

    def test_stockpile_timestamp_auto_generation(self) -> None:
        """Test that timestamp is automatically generated for tracking."""
        before = datetime.now()
        stockpile = Stockpile()
        after = datetime.now()

        # Verify timestamp was generated and is within expected range
        assert isinstance(stockpile.timestamp, datetime)
        assert before <= stockpile.timestamp <= after

    def test_stockpile_equality(self) -> None:
        """Test stockpile equality comparison for business logic."""
        custom_time = datetime(2024, 1, 4, 9, 0, 0)
        items = [StockpileItem(code="BasicMaterialsIcon", quantity=100)]

        stockpile1 = Stockpile(
            name="Test", type=StockpileType.SEAPORT, items=items, timestamp=custom_time
        )

        stockpile2 = Stockpile(
            name="Test", type=StockpileType.SEAPORT, items=items, timestamp=custom_time
        )

        stockpile3 = Stockpile(
            name="Different", type=StockpileType.SEAPORT, items=items, timestamp=custom_time
        )

        assert stockpile1 == stockpile2
        assert stockpile1 != stockpile3

    def test_stockpile_copy(self) -> None:
        """Test stockpile copying for data manipulation."""
        original = Stockpile(
            name="Original",
            type=StockpileType.SEAPORT,
            items=[StockpileItem(code="TestIcon", quantity=100)],
        )

        # Test shallow copy (default)
        copied = original.model_copy()
        assert copied == original
        assert copied is not original
        assert copied.items is original.items  # Shallow copy shares list reference

        # Test deep copy
        deep_copied = original.model_copy(deep=True)
        assert deep_copied == original
        assert deep_copied is not original
        assert deep_copied.items is not original.items  # Deep copy creates new list

    def test_stockpile_update(self) -> None:
        """Test stockpile field updates for data processing."""
        stockpile = Stockpile(name="Original")

        updated = stockpile.model_copy(update={"name": "Updated", "shard": "NEW"})

        assert updated.name == "Updated"
        assert updated.shard == "NEW"
        assert stockpile.name == "Original"  # Original unchanged

    def test_to_key_matches_fs_sav(self) -> None:
        """The key is fs-sav's: type:hex:x,y:name with 4-decimal coordinates."""
        stockpile = Stockpile(
            name="Logi",
            type=StockpileType.SEAPORT,
            hex="Westgate",
            coords=StockpileCoords(x=0.4577456, y=0.66),
        )
        assert stockpile.to_key() == "Seaport:Westgate:0.4577,0.6600:Logi"

    def test_to_key_without_location(self) -> None:
        """Missing hex and coords fall back to empty hex and 0,0."""
        assert Stockpile(type=StockpileType.SEAPORT).to_key() == "Seaport::0,0:"
