"""Tests for the global hotkey spec conversion."""

import pytest

from foxhole_stockpiles.gui.utils.hotkey_listener import to_global_hotkey


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
