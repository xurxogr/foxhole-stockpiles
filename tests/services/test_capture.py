"""Tests for the screenshot capture service."""

import sys
import types
from typing import Any

import pytest

from foxhole_stockpiles.services.capture import CaptureError, capture_window


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
