"""Tests for the global hotkey spec conversion and listener."""

from unittest.mock import MagicMock

import pytest

from foxhole_stockpiles.gui.utils import hotkey_listener
from foxhole_stockpiles.gui.utils.hotkey_listener import (
    HotkeyListener,
    global_hotkeys_supported,
    to_global_hotkey,
)


def _fake_keyboard(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Back the listener with a mock ``pynput.keyboard``."""
    keyboard = MagicMock()
    monkeypatch.setattr(hotkey_listener, "PYNPUT_AVAILABLE", True)
    monkeypatch.setattr(hotkey_listener, "keyboard", keyboard, raising=False)
    return keyboard


class TestGlobalHotkeysSupported:
    """Environment detection for global hotkeys."""

    def test_false_outside_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Global hotkeys are never supported outside Windows."""
        monkeypatch.setattr(hotkey_listener, "PYNPUT_AVAILABLE", True)
        assert global_hotkeys_supported(platform="linux") is False
        assert global_hotkeys_supported(platform="darwin") is False

    def test_false_without_the_capture_extra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows, global hotkeys need pynput from the capture extra."""
        monkeypatch.setattr(hotkey_listener, "PYNPUT_AVAILABLE", False)
        assert global_hotkeys_supported(platform="win32") is False

    def test_true_on_windows_with_the_extra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Windows with pynput installed supports global hotkeys."""
        monkeypatch.setattr(hotkey_listener, "PYNPUT_AVAILABLE", True)
        assert global_hotkeys_supported(platform="win32") is True


class TestHotkeyListener:
    """Listener lifecycle (start/stop) over a mocked pynput backend."""

    def test_init_converts_keys(self) -> None:
        """The listener stores every converted hotkey spec."""
        listener = HotkeyListener({"ctrl+s": lambda: None, "F9": lambda: None})
        assert "<ctrl>+s" in listener._bindings
        assert "<f9>" in listener._bindings

    def test_init_empty_raises(self) -> None:
        """An empty bindings mapping raises ValueError."""
        with pytest.raises(ValueError):
            HotkeyListener({})

    def test_start_registers_hotkeys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() registers all bindings with the backend and starts it."""
        keyboard = _fake_keyboard(monkeypatch)
        listener = HotkeyListener({"F9": lambda: None, "ctrl+v": lambda: None})
        listener.start()
        keyboard.GlobalHotKeys.assert_called_once()
        registered = keyboard.GlobalHotKeys.call_args.args[0]
        assert set(registered) == {"<f9>", "<ctrl>+v"}
        keyboard.GlobalHotKeys.return_value.start.assert_called_once()

    def test_start_raises_without_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """start() raises RuntimeError when pynput is not installed."""
        monkeypatch.setattr(hotkey_listener, "PYNPUT_AVAILABLE", False)
        listener = HotkeyListener({"F9": lambda: None})
        with pytest.raises(RuntimeError):
            listener.start()

    def test_stop_after_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """stop() stops the backend listener and clears it."""
        keyboard = _fake_keyboard(monkeypatch)
        listener = HotkeyListener({"F9": lambda: None})
        listener.start()
        listener.stop()
        keyboard.GlobalHotKeys.return_value.stop.assert_called_once()
        assert listener._listener is None

    def test_stop_without_start_is_noop(self) -> None:
        """stop() is a no-op when never started."""
        HotkeyListener({"F9": lambda: None}).stop()


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
