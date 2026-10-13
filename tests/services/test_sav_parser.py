"""Tests for services.sav_parser module."""

import logging
import warnings
from collections.abc import Callable
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


class TestParseSaveWarnings:
    """fs-sav warnings are logged instead of reaching stderr."""

    SKIPPED = (
        "TownBase1 at DeadLandsHex skipped: the game had no details for it when it was last updated"
    )

    def _warn_and_return(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        """Emit an fs-sav style warning and return one stockpile.

        Args:
            *_args (Any): Ignored positional arguments.
            **_kwargs (Any): Ignored keyword arguments.

        Returns:
            list[dict[str, Any]]: One raw stockpile.
        """
        warnings.warn(self.SKIPPED, UserWarning, stacklevel=1)
        return [{"type": "Seaport"}]

    @pytest.mark.parametrize(
        ("fs_sav_function", "call"),
        [
            ("parse_save", lambda: parse_save("x.sav")),
            ("parse_save_bytes", lambda: parse_save_bytes(b"data")),
        ],
    )
    def test_warnings_logged(
        self,
        fs_sav_function: str,
        call: Callable[[], list[Stockpile]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each fs-sav warning becomes a logger warning and is not re-raised."""
        with patch("foxhole_stockpiles.services.sav_parser.fs_sav") as mock_fs_sav:
            getattr(mock_fs_sav, fs_sav_function).side_effect = self._warn_and_return
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                with caplog.at_level(logging.WARNING, logger="foxhole_stockpiles.services"):
                    result = call()

        assert len(result) == 1
        assert [r.getMessage() for r in caplog.records] == [f"fs-sav: {self.SKIPPED}"]


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

    def test_convert_refinery(self) -> None:
        """The refinery block from fs-sav is kept on the stockpile."""
        refinery_data: dict[str, Any] = {
            "orders_access": {"level": "public"},
            "orders": [{"slot": 0, "code": "Cloth", "source": 0, "refined": 50, "duration": 0}],
            "storages": [
                {
                    "access": {"level": "squad", "squad_id": 1},
                    "slot": 1,
                    "code": "Diesel",
                    "refined": 5309,
                }
            ],
        }
        data: dict[str, Any] = {"type": "Refinery", "refinery": refinery_data}

        result = _convert_to_stockpile(data)

        assert result.refinery is not None
        assert result.refinery.model_dump(exclude_none=True) == refinery_data

    def test_convert_factory_orders(self) -> None:
        """The factory_orders block from fs-sav is kept on the stockpile."""
        orders: list[dict[str, Any]] = [
            {
                "queue": 0,
                "queue_type": "SmallArms",
                "duration": 0,
                "items": [{"slot": 16, "code": "RifleC"}],
            },
            {
                "queue": 6,
                "queue_type": "Uniforms",
                "duration": 90,
                "items": [{"slot": 13, "code": "ScoutUniformC"}],
            },
        ]

        result = _convert_to_stockpile({"type": "Factory", "factory_orders": orders})

        assert result.factory_orders is not None
        assert [o.model_dump(exclude_none=True) for o in result.factory_orders] == orders

    def test_convert_factory_order_item_without_code(self) -> None:
        """An order item without code converts with code None."""
        orders = [{"queue": 1, "duration": 30, "items": [{"slot": 255}]}]

        result = _convert_to_stockpile({"type": "MassProduction", "factory_orders": orders})

        assert result.factory_orders is not None
        assert result.factory_orders[0].queue_type is None
        assert result.factory_orders[0].items[0].slot == 255
        assert result.factory_orders[0].items[0].code is None

    def test_convert_factory_orders_absent(self) -> None:
        """A factory without the factory_orders block converts with None."""
        result = _convert_to_stockpile({"type": "Factory"})

        assert result.type == StockpileType.FACTORY
        assert result.factory_orders is None

    def test_convert_tech(self) -> None:
        """The tech block from fs-sav is kept on the stockpile."""
        data: dict[str, Any] = {
            "type": "FortBaseT1",
            "tech": {"ProvisionalGarrison": 100, "SmallGarrison": 40, "T1Garrison": 0},
        }

        result = _convert_to_stockpile(data)

        assert result.tech is not None
        assert result.tech.model_dump(exclude_none=True) == {
            "provisional_garrison": 100,
            "small_garrison": 40,
            "t1_garrison": 0,
        }

    def test_convert_tech_absent(self) -> None:
        """A base without the tech block converts with tech None."""
        result = _convert_to_stockpile({"type": "FortBaseT1"})

        assert result.tech is None

    def test_convert_refinery_absent(self) -> None:
        """A Refinery without the refinery block converts with refinery None."""
        result = _convert_to_stockpile({"type": "Refinery"})

        assert result.type == StockpileType.REFINERY
        assert result.refinery is None


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
