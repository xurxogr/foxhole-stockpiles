"""Tests for the CaptureKeyDialog hotkey-capture dialog."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog

from foxhole_stockpiles.gui.widgets.capture_key_dialog import CaptureKeyDialog


@pytest.fixture
def dialog(qtbot: Any) -> CaptureKeyDialog:
    """Construct a CaptureKeyDialog registered with qtbot."""
    d = CaptureKeyDialog()
    qtbot.addWidget(d)
    return d


def _key_event(
    key: Qt.Key, mods: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
) -> QKeyEvent:
    """Build a key-press event."""
    return QKeyEvent(QEvent.Type.KeyPress, key, mods)


def test_construction(dialog: CaptureKeyDialog) -> None:
    """The dialog starts with no captured key."""
    assert dialog.key_text is None
    assert dialog.isModal()


def test_none_event_ignored(dialog: CaptureKeyDialog) -> None:
    """A None event is a no-op."""
    dialog.keyPressEvent(None)
    assert dialog.key_text is None


def test_modifier_only_ignored(dialog: CaptureKeyDialog) -> None:
    """A bare modifier press is ignored (waits for a real key)."""
    dialog.keyPressEvent(_key_event(Qt.Key.Key_Control))
    assert dialog.key_text is None


def test_escape_rejects(dialog: CaptureKeyDialog) -> None:
    """Escape cancels the dialog without capturing a key."""
    dialog.keyPressEvent(_key_event(Qt.Key.Key_Escape))
    assert dialog.key_text is None
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_normal_key_captured(dialog: CaptureKeyDialog) -> None:
    """A non-modifier key with held modifiers is captured and accepted."""
    dialog.keyPressEvent(_key_event(Qt.Key.Key_F3, Qt.KeyboardModifier.ControlModifier))
    assert dialog.key_text
    assert dialog.result() == QDialog.DialogCode.Accepted
