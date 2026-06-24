"""Tests for services.sav_parser module."""

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.sav_parser import (
    _convert_to_stockpile,
    info,
    parse_save,
    parse_save_bytes,
)


class TestParseSaveErrors:
    """Error and bytes paths for the fs-sav wrapper."""

    def test_parse_save_non_list_raises(self) -> None:
        """A non-list result from fs_sav.parse_save raises RuntimeError."""
        with patch("foxhole_stockpiles.services.sav_parser.fs_sav") as mock_fs_sav:
            mock_fs_sav.parse_save.return_value = {"not": "a list"}
            with pytest.raises(RuntimeError, match="unexpected type"):
                parse_save("x.sav")

    def test_parse_save_bytes_converts(self) -> None:
        """parse_save_bytes converts each raw stockpile dict."""
        raw = [{"type": "Seaport", "name": "P", "items": []}]
        with patch("foxhole_stockpiles.services.sav_parser.fs_sav") as mock_fs_sav:
            mock_fs_sav.parse_save_bytes.return_value = raw
            result = parse_save_bytes(b"data", public=True, hex_filter="H")
        assert len(result) == 1
        assert result[0].type == StockpileType.SEAPORT
        mock_fs_sav.parse_save_bytes.assert_called_once()

    def test_parse_save_bytes_non_list_raises(self) -> None:
        """A non-list result from fs_sav.parse_save_bytes raises RuntimeError."""
        with patch("foxhole_stockpiles.services.sav_parser.fs_sav") as mock_fs_sav:
            mock_fs_sav.parse_save_bytes.return_value = None
            with pytest.raises(RuntimeError, match="unexpected type"):
                parse_save_bytes(b"data")


class TestConvertTimestampFallback:
    """Timestamp parsing fallback."""

    def test_invalid_timestamp_falls_back_to_now(self) -> None:
        """An unparseable timestamp falls back to the current time."""
        stockpile = _convert_to_stockpile({"type": "Seaport", "timestamp": "not-a-date"})
        assert isinstance(stockpile.timestamp, datetime)

    def test_non_string_timestamp_falls_back_to_now(self) -> None:
        """A non-string timestamp (no .replace) falls back to the current time."""
        stockpile = _convert_to_stockpile({"type": "Seaport", "timestamp": 12345})
        assert isinstance(stockpile.timestamp, datetime)


class TestInfo:
    """Test suite for info function."""

    def test_info_returns_rust_implementation(self) -> None:
        """Test that info returns rust implementation."""
        result = info()
        assert result["implementation"] == "rust"
        assert "version" in result


class TestConvertToStockpile:
    """Test suite for _convert_to_stockpile function."""

    def test_convert_basic_stockpile(self) -> None:
        """Test converting a basic stockpile dict to Stockpile model."""
        data = {
            "name": "",
            "type": "Seaport",
            "hex": "TerminusHex",
            "coords": {"x": 0.5, "y": 0.6},
            "is_reserve": False,
            "items": [
                {"code": "Rifle", "quantity": 100, "crated": False},
                {"code": "RifleAmmo", "quantity": 50, "crated": True},
            ],
            "timestamp": "2024-01-15T10:30:00Z",
        }

        result = _convert_to_stockpile(data)

        assert isinstance(result, Stockpile)
        assert result.name == ""
        assert result.type == StockpileType.SEAPORT
        assert result.hex == "TerminusHex"
        assert result.coords is not None
        assert result.coords.x == 0.5
        assert result.coords.y == 0.6
        assert result.is_reserve is False
        assert len(result.items) == 2
        assert result.items[0].code == "Rifle"
        assert result.items[0].quantity == 100
        assert result.items[0].crated is False
        assert result.items[1].crated is True

    def test_convert_faction_normalized(self) -> None:
        """A faction from fs-sav is normalized onto the stockpile."""
        data: dict[str, Any] = {"type": "Seaport", "faction": "EFactionId::Wardens"}
        assert _convert_to_stockpile(data).faction == ItemFaction.WARDENS

    def test_convert_faction_none_when_absent(self) -> None:
        """A missing faction key leaves the field None (omitted from output)."""
        data: dict[str, Any] = {"type": "Seaport"}
        assert _convert_to_stockpile(data).faction is None

    def test_convert_reserve_stockpile(self) -> None:
        """Test converting a reserve stockpile."""
        data: dict[str, Any] = {
            "name": "Logi Reserve",
            "type": "StorageFacility",
            "hex": "DeadlandsHex",
            "coords": None,
            "is_reserve": True,
            "items": [],
            "timestamp": "2024-01-15T10:30:00+00:00",
        }

        result = _convert_to_stockpile(data)

        assert result.name == "Logi Reserve"
        assert result.type == StockpileType.STORAGE_DEPOT
        assert result.is_reserve is True
        assert result.coords is None

    def test_convert_unknown_stockpile_type_passes_through(self) -> None:
        """An unrecognized type from fs-sav is preserved verbatim."""
        data: dict[str, Any] = {
            "name": "",
            "type": "UnknownType",
            "hex": None,
            "coords": None,
            "is_reserve": False,
            "items": [],
            "timestamp": "2024-01-15T10:30:00Z",
        }

        result = _convert_to_stockpile(data)

        assert result.type == "UnknownType"


class TestParseSave:
    """Test suite for parse_save function."""

    def test_parse_save_calls_fs_sav(self) -> None:
        """Test that parse_save calls fs_sav.parse_save."""
        mock_raw_data = [
            {
                "name": "",
                "type": "Seaport",
                "hex": "TerminusHex",
                "coords": {"x": 0.5, "y": 0.6},
                "is_reserve": False,
                "items": [],
                "timestamp": "2024-01-15T10:30:00Z",
            }
        ]

        with patch("foxhole_stockpiles.services.sav_parser.fs_sav") as mock_fs_sav:
            mock_fs_sav.parse_save.return_value = mock_raw_data

            result = parse_save(Path("/test/file.sav"))

            mock_fs_sav.parse_save.assert_called_once_with(
                "/test/file.sav",
                public=False,
                reserves=False,
                hex=None,
                stockpile_type=None,
                with_items=False,
            )
            assert len(result) == 1
            assert isinstance(result[0], Stockpile)

    def test_parse_save_with_filters(self) -> None:
        """Test that filters are passed to fs_sav."""
        with patch("foxhole_stockpiles.services.sav_parser.fs_sav") as mock_fs_sav:
            mock_fs_sav.parse_save.return_value = []

            parse_save(
                Path("/test/file.sav"),
                public=True,
                hex_filter="TerminusHex",
                stockpile_type="Seaport",
            )

            mock_fs_sav.parse_save.assert_called_once_with(
                "/test/file.sav",
                public=True,
                reserves=False,
                hex="TerminusHex",
                stockpile_type="Seaport",
                with_items=False,
            )
