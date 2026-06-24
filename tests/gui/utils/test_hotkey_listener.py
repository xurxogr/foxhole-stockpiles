"""Tests for the global hotkey spec conversion and listener."""

import platform
import sys
import types
from unittest.mock import MagicMock

import pytest

from foxhole_stockpiles.gui.utils.hotkey_listener import (
    HotkeyListener,
    global_hotkeys_supported,
    to_global_hotkey,
)


def _set_release(monkeypatch: pytest.MonkeyPatch, release: str) -> None:
    """Pin ``platform.uname().release`` for the supported-environment check."""
    monkeypatch.setattr(platform, "uname", lambda: types.SimpleNamespace(release=release))


def _fake_pynput(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Inject a fake ``pynput`` module exposing a mock ``keyboard``."""
    keyboard = MagicMock()
    module = types.ModuleType("pynput")
    module.keyboard = keyboard  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", module)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)
    return keyboard


class TestGlobalHotkeysSupported:
    """Environment detection for global hotkeys."""

    def test_false_on_wsl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A WSL kernel release disables global hotkeys."""
        _set_release(monkeypatch, "5-microsoft")
        assert global_hotkeys_supported() is False

    def test_false_when_pynput_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No pynput backend disables global hotkeys."""
        _set_release(monkeypatch, "6-generic")
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
        monkeypatch.setitem(sys.modules, "pynput", None)
        assert global_hotkeys_supported() is False

    def test_true_when_supported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-WSL host with pynput available enables global hotkeys."""
        _set_release(monkeypatch, "6-generic")
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
        _fake_pynput(monkeypatch)
        assert global_hotkeys_supported() is True


class TestHotkeyListener:
    """Listener lifecycle (start/stop) over a mocked pynput backend."""

    def test_init_converts_key(self) -> None:
        """The listener stores the converted hotkey spec."""
        listener = HotkeyListener("ctrl+s", lambda: None)
        assert listener._hotkey == "<ctrl>+s"

    def test_start_registers_hotkey(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() registers the hotkey with the backend and starts it."""
        keyboard = _fake_pynput(monkeypatch)
        listener = HotkeyListener("F9", lambda: None)
        listener.start()
        keyboard.GlobalHotKeys.assert_called_once()
        keyboard.GlobalHotKeys.return_value.start.assert_called_once()

    def test_start_raises_without_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() raises RuntimeError when pynput cannot be loaded."""
        monkeypatch.setitem(sys.modules, "pynput", None)
        listener = HotkeyListener("F9", lambda: None)
        with pytest.raises(RuntimeError):
            listener.start()

    def test_stop_after_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """stop() stops the backend listener and clears it."""
        keyboard = _fake_pynput(monkeypatch)
        listener = HotkeyListener("F9", lambda: None)
        listener.start()
        listener.stop()
        keyboard.GlobalHotKeys.return_value.stop.assert_called_once()
        assert listener._listener is None

    def test_stop_without_start_is_noop(self) -> None:
        """stop() is a no-op when never started."""
        HotkeyListener("F9", lambda: None).stop()


def test_function_key() -> None:
    """Function keys are wrapped in angle brackets and lowercased."""
    assert to_global_hotkey("F9") == "<f9>"


def test_single_character() -> None:
    """Single characters are passed through lowercased."""
    assert to_global_hotkey("a") == "a"


def test_combination() -> None:
    """Combinations join members with '+', wrapping named keys."""
    assert to_global_hotkey("ctrl+shift+s") == "<ctrl>+<shift>+s"


def test_modifier_with_function_key() -> None:
    """A modifier combined with a function key is converted (Qt 'Ctrl+F3')."""
    assert to_global_hotkey("Ctrl+F3") == "<ctrl>+<f3>"


def test_meta_aliases_to_cmd() -> None:
    """The Meta/Super/Win key maps to pynput's 'cmd'."""
    assert to_global_hotkey("Meta+S") == "<cmd>+s"


def test_empty_raises() -> None:
    """An empty spec raises ValueError."""
    with pytest.raises(ValueError):
        to_global_hotkey("")
