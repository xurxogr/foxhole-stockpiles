"""Tests for the Scanner seam over the external Rust ``fs_ocr`` engine.

The external engine is mocked so these tests cover the adapter logic: image
coercion, external→runtime stockpile conversion, faction mapping, and the
constructor's validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.services import scanner as scanner_mod
from foxhole_stockpiles.services.scanner import (
    Scanner,
    _coerce_image,
    build_scanner,
    to_runtime_stockpile,
)


def _convert(fake: object) -> Any:
    """Adapt a fake external stockpile, bypassing the fs_ocr.Stockpile type."""
    return to_runtime_stockpile(cast(Any, fake))


class FakeCandidate:
    """Stand-in for fs_ocr candidate."""

    def __init__(self, code: str, confidence: float) -> None:
        """Store the fake candidate fields."""
        self.code = code
        self.confidence = confidence


class FakeItem:
    """Stand-in for fs_ocr.StockpileItem."""

    def __init__(
        self,
        code: str = "RifleW",
        quantity: int = 3,
        crated: bool = True,
        confidence: float = 0.9,
        x: int = 1,
        y: int = 2,
        candidates: list[FakeCandidate] | None = None,
    ) -> None:
        """Store the fake item fields."""
        self.code = code
        self.quantity = quantity
        self.crated = crated
        self.confidence = confidence
        self.x = x
        self.y = y
        self.candidates = candidates


class FakeExternalStockpile:
    """Stand-in for fs_ocr.Stockpile."""

    def __init__(
        self,
        type_name: str = "Seaport",
        name: str = "Public",
        items: list[FakeItem] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        """Store the fake stockpile fields."""
        self._type_name = type_name
        self.name = name
        self.is_reserve = False
        self.items = items if items is not None else [FakeItem()]
        self.errors = errors if errors is not None else []
        self.shard = "ABLE"
        self.ingame_timestamp = "Day 1"
        self.resolution = "1920x1080"

    def to_json(self) -> str:
        """Return JSON carrying only the ``type`` field the adapter reads."""
        return json.dumps({"type": self._type_name})


class TestCoerceImage:
    """_coerce_image input handling."""

    def test_ndarray_passthrough(self) -> None:
        """An ndarray is returned as a uint8 array."""
        arr = np.zeros((2, 2, 3), dtype=np.uint8)
        assert _coerce_image(arr).dtype == np.uint8

    def test_bytes_decoded(self) -> None:
        """Bytes are decoded via decode_bgr."""
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        with patch.object(scanner_mod, "decode_bgr", return_value=arr) as dec:
            assert _coerce_image(b"data") is arr
            dec.assert_called_once()

    def test_bytes_decode_failure_raises(self) -> None:
        """A failed decode raises ValueError."""
        with (
            patch.object(scanner_mod, "decode_bgr", return_value=None),
            pytest.raises(ValueError, match="decode"),
        ):
            _coerce_image(b"bad")

    def test_path_read(self, tmp_path: Path) -> None:
        """A path is read via read_bgr."""
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        with patch.object(scanner_mod, "read_bgr", return_value=arr) as rd:
            assert _coerce_image(tmp_path / "x.png") is arr
            rd.assert_called_once()

    def test_path_read_failure_raises(self) -> None:
        """A failed read raises ValueError."""
        with (
            patch.object(scanner_mod, "read_bgr", return_value=None),
            pytest.raises(ValueError, match="read"),
        ):
            _coerce_image("missing.png")


class TestToRuntimeStockpile:
    """External→runtime conversion."""

    def test_basic_fields_and_type_mapping(self) -> None:
        """Known external type names map to the runtime type."""
        sp = _convert(FakeExternalStockpile(type_name="Seaport", name="Logi"))
        assert sp.name == "Logi"
        assert sp.type == StockpileType.SEAPORT
        assert len(sp.items) == 1
        assert sp.shard == "ABLE"
        assert sp.resolution == "1920x1080"

    def test_unknown_type_falls_back_to_undefined(self) -> None:
        """An unknown external type name becomes UNDEFINED."""
        sp = _convert(FakeExternalStockpile(type_name="Atlantis"))
        assert sp.type == StockpileType.UNDEFINED

    def test_items_with_candidates(self) -> None:
        """Item candidates are adapted to runtime ItemCandidate objects."""
        item = FakeItem(candidates=[FakeCandidate("A", 0.8), FakeCandidate("B", 0.7)])
        sp = _convert(FakeExternalStockpile(items=[item]))
        assert sp.items[0].candidates is not None
        assert len(sp.items[0].candidates) == 2

    def test_items_without_candidates(self) -> None:
        """An item with no candidates yields None candidates."""
        sp = _convert(FakeExternalStockpile(items=[FakeItem(candidates=None)]))
        assert sp.items[0].candidates is None

    def test_empty_errors_become_none(self) -> None:
        """An empty error list is normalized to None."""
        sp = _convert(FakeExternalStockpile(errors=[]))
        assert sp.errors is None

    def test_errors_preserved(self) -> None:
        """A non-empty error list is preserved."""
        sp = _convert(FakeExternalStockpile(errors=["bad icon"]))
        assert sp.errors == ["bad icon"]


def _fake_fs_ocr() -> MagicMock:
    """Build a mock fs_ocr module whose scanner returns a fake stockpile."""
    mod = MagicMock()
    inner = MagicMock()
    inner.scan.return_value = FakeExternalStockpile()
    mod.StockpileScanner.return_value = inner
    return mod


class TestScannerConstructor:
    """Scanner.__init__ validation."""

    def test_missing_database_path_raises(self) -> None:
        """No database_path → ValueError."""
        with pytest.raises(ValueError, match="database_path"):
            Scanner(ScannerSettings(database_path=None))

    def test_nonexistent_database_raises(self, tmp_path: Path) -> None:
        """A configured-but-missing database → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Scanner(ScannerSettings(database_path=tmp_path / "nope.h5"))

    def test_constructs_and_configures_engine(self, tmp_path: Path) -> None:
        """A valid path constructs the engine and applies the config."""
        db = tmp_path / "db.h5"
        db.write_text("x")
        fake = _fake_fs_ocr()
        with patch.object(scanner_mod, "fs_ocr", fake):
            Scanner(ScannerSettings(database_path=db, confidence_gap=0.05))
        fake.StockpileScanner.assert_called_once()
        fake.StockpileScanner.return_value.set_config.assert_called_once()


class TestScannerScan:
    """Scanner.scan / scan_sync behavior."""

    def _make(self, tmp_path: Path) -> tuple[Scanner, MagicMock]:
        db = tmp_path / "db.h5"
        db.write_text("x")
        fake = _fake_fs_ocr()
        with patch.object(scanner_mod, "fs_ocr", fake):
            sc = Scanner(ScannerSettings(database_path=db))
        return sc, fake

    async def test_scan_async_adapts_result(self, tmp_path: Path) -> None:
        """scan() returns an adapted runtime Stockpile."""
        sc, _ = self._make(tmp_path)
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        sp = await sc.scan(arr)
        assert sp.type == StockpileType.SEAPORT

    def test_scan_sync_adapts_result(self, tmp_path: Path) -> None:
        """scan_sync() returns an adapted runtime Stockpile."""
        sc, _ = self._make(tmp_path)
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        sp = sc.scan_sync(arr)
        assert sp.type == StockpileType.SEAPORT

    def test_faction_mapping_wardens(self, tmp_path: Path) -> None:
        """WARDENS maps to the 'wardens' external filter."""
        sc, _ = self._make(tmp_path)
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        sc.scan_sync(arr, faction=ItemFaction.WARDENS)
        _img, ext_faction = cast(MagicMock, sc._scanner).scan.call_args[0]
        assert ext_faction == "wardens"

    def test_faction_neutral_maps_to_no_filter(self, tmp_path: Path) -> None:
        """NEUTRAL applies no filter (None)."""
        sc, _ = self._make(tmp_path)
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        sc.scan_sync(arr, faction=ItemFaction.NEUTRAL)
        _img, ext_faction = cast(MagicMock, sc._scanner).scan.call_args[0]
        assert ext_faction is None

    def test_no_faction_maps_to_no_filter(self, tmp_path: Path) -> None:
        """No faction applies no filter (None)."""
        sc, _ = self._make(tmp_path)
        arr = np.zeros((1, 1, 3), dtype=np.uint8)
        sc.scan_sync(arr)
        _img, ext_faction = cast(MagicMock, sc._scanner).scan.call_args[0]
        assert ext_faction is None


class TestBuildScanner:
    """build_scanner factory."""

    def test_returns_scanner(self, tmp_path: Path) -> None:
        """build_scanner returns a Scanner instance."""
        db = tmp_path / "db.h5"
        db.write_text("x")
        with patch.object(scanner_mod, "fs_ocr", _fake_fs_ocr()):
            sc = build_scanner(ScannerSettings(database_path=db))
        assert isinstance(sc, Scanner)
