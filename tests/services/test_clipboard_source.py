"""Tests for the ClipboardSource reader."""

from unittest.mock import patch

from foxhole_stockpiles.services.clipboard_source import ClipboardSource

_PASTE = "foxhole_stockpiles.services.clipboard_source.pyperclip.paste"


def test_read_returns_clipboard_text() -> None:
    """read() returns whatever pyperclip provides."""
    with patch(_PASTE, return_value="hello"):
        assert ClipboardSource().read() == "hello"


def test_read_returns_none_on_backend_error() -> None:
    """A backend failure is swallowed and reported as None."""
    with patch(_PASTE, side_effect=Exception("no backend")):
        assert ClipboardSource().read() is None
