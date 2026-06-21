"""Tests for the screenshot capture service."""

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.capture import CaptureError, capture_window, save_screenshot


class _FakeWindow:
    """Minimal stand-in for a pywinctl window."""

    def __init__(self, *, minimized: bool = False, active: bool = True) -> None:
        self.isMinimized = minimized
        self.isActive = active

    def getClientFrame(self) -> tuple[int, int, int, int]:
        return (0, 0, 10, 10)


def _fake_pywinctl(windows: list[Any]) -> types.ModuleType:
    module = types.ModuleType("pywinctl")

    class _Re:
        STARTSWITH = "startswith"

    module.Re = _Re  # type: ignore[attr-defined]
    module.getWindowsWithTitle = lambda title, condition=None: windows  # type: ignore[attr-defined]
    return module


def test_capture_unavailable_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing window backend raises CaptureError."""
    monkeypatch.setitem(sys.modules, "pywinctl", None)
    with pytest.raises(CaptureError, match="not available"):
        capture_window()


def test_capture_no_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """No matching window raises CaptureError."""
    monkeypatch.setitem(sys.modules, "pywinctl", _fake_pywinctl([]))
    with pytest.raises(CaptureError, match="No window"):
        capture_window()


def test_capture_minimized(monkeypatch: pytest.MonkeyPatch) -> None:
    """A minimized window raises CaptureError."""
    monkeypatch.setitem(sys.modules, "pywinctl", _fake_pywinctl([_FakeWindow(minimized=True)]))
    with pytest.raises(CaptureError, match="minimized"):
        capture_window()


def test_capture_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-active window raises CaptureError."""
    monkeypatch.setitem(sys.modules, "pywinctl", _fake_pywinctl([_FakeWindow(active=False)]))
    with pytest.raises(CaptureError, match="active"):
        capture_window()


def test_capture_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid active window returns the encoded PNG bytes."""
    monkeypatch.setitem(sys.modules, "pywinctl", _fake_pywinctl([_FakeWindow()]))

    from PIL import ImageGrab

    class _FakeImage:
        def save(self, buffer: Any, format: str) -> None:  # noqa: A002 - PIL kw name
            buffer.write(b"PNGDATA")

    monkeypatch.setattr(ImageGrab, "grab", lambda bbox, all_screens: _FakeImage())

    data = capture_window()
    assert data == b"PNGDATA"


def test_save_screenshot_empty_folder_returns_none(tmp_path: Path) -> None:
    """An empty folder disables saving and returns None."""
    assert save_screenshot(b"PNGDATA", "") is None


def test_save_screenshot_writes_descriptive_file(tmp_path: Path) -> None:
    """Saving writes the bytes into a per-day subfolder with a descriptive name."""
    stockpile = Stockpile(
        name="Logi",
        resolution="1920x1080",
        items=[StockpileItem(code="RifleW", quantity=10)],
    )

    path = save_screenshot(b"PNGDATA", tmp_path, stockpile)

    assert path is not None
    assert path.exists()
    assert path.read_bytes() == b"PNGDATA"
    assert path.suffix == ".png"
    # Per-day subfolder (YYYY-MM-DD) under the target folder.
    assert path.parent.parent == tmp_path
    assert "Logi" in path.name
    assert "1920x1080" in path.name


def test_save_screenshot_without_stockpile(tmp_path: Path) -> None:
    """Saving without a stockpile still writes a timestamped file."""
    path = save_screenshot(b"PNGDATA", tmp_path)

    assert path is not None
    assert path.exists()
    assert path.read_bytes() == b"PNGDATA"
