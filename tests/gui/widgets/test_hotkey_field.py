"""Tests for the HotkeyField widget."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog

from foxhole_stockpiles.gui.widgets import hotkey_field as mod
from foxhole_stockpiles.gui.widgets.hotkey_field import HotkeyField


@pytest.fixture
def field(qtbot: Any) -> HotkeyField:
    """Construct a HotkeyField registered with qtbot."""
    widget = HotkeyField()
    qtbot.addWidget(widget)
    return widget


def test_display_is_read_only(field: HotkeyField) -> None:
    """The hotkey can only change through the buttons."""
    assert field.display.isReadOnly() is True


def test_set_key_shows_it(field: HotkeyField) -> None:
    """A set key is stored and displayed."""
    field.set_key("F9")
    assert field.key() == "F9"
    assert field.display.text() == "F9"


def test_set_key_none_shows_nothing(field: HotkeyField) -> None:
    """Setting no key empties the display."""
    field.set_key("F9")
    field.set_key(None)
    assert field.key() is None
    assert field.display.text() == ""


def test_empty_key_reads_as_none(field: HotkeyField) -> None:
    """An empty key is the same as no key."""
    field.set_key("")
    assert field.key() is None


def test_change_accepted(field: HotkeyField) -> None:
    """Accepting the key dialog stores and displays the hotkey."""
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.key_text = "<ctrl>+s"
    with patch.object(mod, "CaptureKeyDialog", return_value=dialog):
        field.change_button.click()
    assert field.key() == "<ctrl>+s"
    assert field.display.text() == "<ctrl>+s"


def test_change_cancelled(field: HotkeyField) -> None:
    """Rejecting the key dialog keeps the existing hotkey."""
    field.set_key("F1")
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected
    with patch.object(mod, "CaptureKeyDialog", return_value=dialog):
        field.change_button.click()
    assert field.key() == "F1"


def test_change_accepted_without_key(field: HotkeyField) -> None:
    """A dialog accepted with no key keeps the existing hotkey."""
    field.set_key("F1")
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.key_text = ""
    with patch.object(mod, "CaptureKeyDialog", return_value=dialog):
        field.change()
    assert field.key() == "F1"


def test_clear_button(field: HotkeyField) -> None:
    """Clearing removes the configured hotkey."""
    field.set_key("F9")
    field.clear_button.click()
    assert field.key() is None
    assert field.display.text() == ""


def test_retranslate(field: HotkeyField) -> None:
    """Retranslating updates the placeholder and both button labels."""
    field.retranslate(placeholder="none", change_text="Set")
    assert field.display.placeholderText() == "none"
    assert field.change_button.text() == "Set"
    assert field.clear_button.text() != ""
