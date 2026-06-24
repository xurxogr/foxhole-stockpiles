"""Tests for the SAV processing config tab's interactive handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog

from foxhole_stockpiles.gui.widgets.config_tabs import sav_processing_tab as mod
from foxhole_stockpiles.gui.widgets.config_tabs.sav_processing_tab import SavProcessingTab

_TAB_MODULE = "foxhole_stockpiles.gui.widgets.config_tabs.sav_processing_tab"
_FILE_DIALOG = f"{_TAB_MODULE}.QFileDialog.getOpenFileName"


@pytest.fixture
def tab(qtbot: Any) -> SavProcessingTab:
    """Construct a SavProcessingTab registered with qtbot."""
    widget = SavProcessingTab()
    qtbot.addWidget(widget)
    return widget


def test_auto_detect_found(tab: SavProcessingTab, monkeypatch: pytest.MonkeyPatch) -> None:
    """A detected save file populates the path input."""
    monkeypatch.setattr(mod, "auto_detect_savefile", lambda: Path("/saves/World_MapData.sav"))
    tab._auto_detect_sav_file()
    assert tab.sav_file_input.text() == str(Path("/saves/World_MapData.sav"))


def test_auto_detect_not_found(tab: SavProcessingTab, monkeypatch: pytest.MonkeyPatch) -> None:
    """No detected file shows an information dialog."""
    monkeypatch.setattr(mod, "auto_detect_savefile", lambda: None)
    with patch.object(mod, "QMessageBox") as message_box:
        tab._auto_detect_sav_file()
    message_box.information.assert_called_once()


def test_browse_sets_path(tab: SavProcessingTab) -> None:
    """Browsing sets the chosen file path."""
    with patch(_FILE_DIALOG, return_value=("/p/World.sav", "")):
        tab._browse_sav_file()
    assert tab.sav_file_input.text() == "/p/World.sav"


def test_browse_cancelled(tab: SavProcessingTab) -> None:
    """Cancelling the browse dialog leaves the path unchanged."""
    tab.sav_file_input.setText("keep")
    with patch(_FILE_DIALOG, return_value=("", "")):
        tab._browse_sav_file()
    assert tab.sav_file_input.text() == "keep"


def test_clear_file(tab: SavProcessingTab) -> None:
    """Clearing empties the path input."""
    tab.sav_file_input.setText("x")
    tab._clear_sav_file()
    assert tab.sav_file_input.text() == ""


def test_change_key_accepted(tab: SavProcessingTab) -> None:
    """Accepting the key dialog stores and displays the hotkey."""
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.key_text = "<ctrl>+s"
    with patch.object(mod, "CaptureKeyDialog", return_value=dialog):
        tab._change_sav_key()
    assert tab.sav_key_display.text() == "<ctrl>+s"
    assert tab._sav_capture_key_value == "<ctrl>+s"


def test_change_key_cancelled(tab: SavProcessingTab) -> None:
    """Rejecting the key dialog keeps the existing hotkey."""
    tab._sav_capture_key_value = "F1"
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Rejected
    with patch.object(mod, "CaptureKeyDialog", return_value=dialog):
        tab._change_sav_key()
    assert tab._sav_capture_key_value == "F1"


def test_clear_key(tab: SavProcessingTab) -> None:
    """Clearing removes the configured hotkey."""
    tab._sav_capture_key_value = "F9"
    tab._clear_sav_key()
    assert tab._sav_capture_key_value is None
    assert tab.sav_key_display.text() == ""


def test_language_change_retranslates(tab: SavProcessingTab) -> None:
    """A language change re-applies translatable strings."""
    tab._on_language_changed("en")
    assert tab.mode_label.text() != ""


def test_set_and_get_values_roundtrip(tab: SavProcessingTab, tmp_path: Path) -> None:
    """set_values loads a settings object and get_values reads it back."""
    from foxhole_stockpiles.core.settings.sections.sav_processing import SavProcessingSettings
    from foxhole_stockpiles.enums.sav_mode import SavMode

    sav = tmp_path / "World.sav"
    sav.write_text("x")
    settings = SavProcessingSettings(
        mode=SavMode.MONITOR,
        sav_capture_key="<ctrl>+d",
        sav_file_path=sav,
        poll_interval=2.0,
        emit_all_on_start=True,
    )
    tab.set_values(settings)
    result = tab.get_values()
    assert result.mode == SavMode.MONITOR
    assert result.sav_capture_key == "<ctrl>+d"
    assert result.sav_file_path == sav
    assert result.poll_interval == 2.0
    assert result.emit_all_on_start is True
