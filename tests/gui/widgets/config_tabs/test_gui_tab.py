"""Tests for GUITab."""

from typing import Any

import pytest

from foxhole_stockpiles.core.settings.sections.gui import GUISettings
from foxhole_stockpiles.gui.widgets.config_tabs.gui_tab import GUITab


@pytest.fixture
def gui_tab(qtbot: Any) -> GUITab:
    """Create a GUITab instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        GUITab: Tab instance
    """
    tab = GUITab()
    qtbot.addWidget(tab)
    return tab


def test_gui_tab_initialization(gui_tab: GUITab) -> None:
    """Test GUITab initialization.

    Args:
        gui_tab: GUITab instance
    """
    assert gui_tab.minimize_to_tray_input is not None
    assert gui_tab.language_input is not None


def test_gui_tab_default_values(gui_tab: GUITab) -> None:
    """Test default values are set correctly.

    Args:
        gui_tab: GUITab instance
    """
    # Minimize to tray should be unchecked by default
    assert not gui_tab.minimize_to_tray_input.isChecked()


def test_gui_tab_set_values(gui_tab: GUITab) -> None:
    """Test setting values from settings object.

    Args:
        gui_tab: GUITab instance
    """
    settings = GUISettings(minimize_to_tray=True)

    gui_tab.set_values(settings)

    assert gui_tab.minimize_to_tray_input.isChecked()


def test_gui_tab_get_values(gui_tab: GUITab) -> None:
    """Test getting values from widgets.

    Args:
        gui_tab: GUITab instance
    """
    gui_tab.minimize_to_tray_input.setChecked(True)

    settings = gui_tab.get_values()

    assert settings.minimize_to_tray is True


def test_gui_tab_minimize_to_tray_toggle(gui_tab: GUITab) -> None:
    """Test minimize to tray checkbox toggle.

    Args:
        gui_tab: GUITab instance
    """
    assert not gui_tab.minimize_to_tray_input.isChecked()

    gui_tab.minimize_to_tray_input.setChecked(True)
    assert gui_tab.minimize_to_tray_input.isChecked()

    gui_tab.minimize_to_tray_input.setChecked(False)
    assert not gui_tab.minimize_to_tray_input.isChecked()


def test_gui_tab_language_input_exists(gui_tab: GUITab) -> None:
    """Test language input exists.

    Args:
        gui_tab: GUITab instance
    """
    assert gui_tab.language_input is not None
    assert gui_tab.language_input.count() >= 1  # At least English


def test_gui_tab_language_set_values(gui_tab: GUITab) -> None:
    """Test setting language from settings.

    Args:
        gui_tab: GUITab instance
    """
    settings = GUISettings(minimize_to_tray=False, language="en")

    gui_tab.set_values(settings)

    assert gui_tab.language_input.currentData() == "en"


def test_gui_tab_language_get_values(gui_tab: GUITab) -> None:
    """Test getting language from widgets.

    Args:
        gui_tab: GUITab instance
    """
    # Find English in the combo box and select it
    for i in range(gui_tab.language_input.count()):
        if gui_tab.language_input.itemData(i) == "en":
            gui_tab.language_input.setCurrentIndex(i)
            break

    settings = gui_tab.get_values()

    assert settings.language == "en"


def test_gui_tab_has_retranslate_method(gui_tab: GUITab) -> None:
    """Test that GUITab has retranslate method.

    Args:
        gui_tab: GUITab instance
    """
    assert hasattr(gui_tab, "retranslate")
    assert callable(gui_tab.retranslate)
    # Should not raise when called
    gui_tab.retranslate()
