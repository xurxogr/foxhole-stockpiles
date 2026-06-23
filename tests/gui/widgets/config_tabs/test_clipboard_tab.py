"""Tests for ClipboardTab."""

from typing import Any

import pytest

from foxhole_stockpiles.core.settings.sections.clipboard import ClipboardSettings
from foxhole_stockpiles.enums.clip_mode import ClipMode
from foxhole_stockpiles.gui.widgets.config_tabs.clipboard_tab import ClipboardTab


@pytest.fixture
def clipboard_tab(qtbot: Any) -> ClipboardTab:
    """Create a ClipboardTab instance.

    Args:
        qtbot: PyQt test fixture.

    Returns:
        ClipboardTab: Tab instance.
    """
    tab = ClipboardTab()
    qtbot.addWidget(tab)
    return tab


def test_initialization(clipboard_tab: ClipboardTab) -> None:
    """The tab builds its widgets.

    Args:
        clipboard_tab: ClipboardTab instance.
    """
    assert clipboard_tab.mode_combo is not None
    assert clipboard_tab.clip_key_display is not None
    assert clipboard_tab.poll_interval_input is not None


def test_set_values(clipboard_tab: ClipboardTab) -> None:
    """Widgets reflect a settings object.

    Args:
        clipboard_tab: ClipboardTab instance.
    """
    clipboard_tab.set_values(
        ClipboardSettings(mode=ClipMode.MONITOR, clip_capture_key="F11", poll_interval=2.5)
    )

    assert clipboard_tab.mode_combo.currentData() == ClipMode.MONITOR
    assert clipboard_tab.clip_key_display.text() == "F11"
    assert clipboard_tab.poll_interval_input.value() == 2.5


def test_get_values_roundtrip(clipboard_tab: ClipboardTab) -> None:
    """get_values returns the configured values.

    Args:
        clipboard_tab: ClipboardTab instance.
    """
    clipboard_tab.set_values(
        ClipboardSettings(mode=ClipMode.MANUAL, clip_capture_key="F9", poll_interval=1.5)
    )

    settings = clipboard_tab.get_values()

    assert settings.mode == ClipMode.MANUAL
    assert settings.clip_capture_key == "F9"
    assert settings.poll_interval == 1.5


def test_clear_hotkey_yields_none(clipboard_tab: ClipboardTab) -> None:
    """Clearing the hotkey produces a None capture key.

    Args:
        clipboard_tab: ClipboardTab instance.
    """
    clipboard_tab.set_values(ClipboardSettings(clip_capture_key="F11"))
    clipboard_tab._clear_clip_key()

    assert clipboard_tab.get_values().clip_capture_key is None


def test_has_retranslate_method(clipboard_tab: ClipboardTab) -> None:
    """The retranslate method exists and runs without error.

    Args:
        clipboard_tab: ClipboardTab instance.
    """
    assert callable(clipboard_tab.retranslate)
    clipboard_tab.retranslate()
