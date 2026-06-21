"""Tests for ScannerTab."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from foxhole_stockpiles.enums.config_level import ConfigLevel
from foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab import ScannerTab


@pytest.fixture
def scanner_tab(qtbot: Any) -> ScannerTab:
    """Create a ScannerTab instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        ScannerTab: Tab instance
    """
    tab = ScannerTab()
    qtbot.addWidget(tab)
    return tab


def test_scanner_tab_initialization(scanner_tab: ScannerTab) -> None:
    """Test ScannerTab initialization.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.database_path_input is not None
    assert scanner_tab.cache_size_input is not None
    assert scanner_tab.early_exit_input is not None
    assert scanner_tab.confidence_gap_input is not None
    assert scanner_tab.debug_mode_input is not None
    assert scanner_tab.extract_icons_input is not None
    assert scanner_tab.screenshots_folder_input is not None


def test_scanner_tab_default_values(scanner_tab: ScannerTab) -> None:
    """Test default values are set correctly.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.cache_size_input.value() == 16
    assert scanner_tab.early_exit_input.value() == 0.0
    assert scanner_tab.confidence_gap_input.value() == 0.0


def test_scanner_tab_cache_size_range(scanner_tab: ScannerTab) -> None:
    """Test cache size input has correct range.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.cache_size_input.minimum() == 0
    assert scanner_tab.cache_size_input.maximum() == 16


def test_scanner_tab_early_exit_range(scanner_tab: ScannerTab) -> None:
    """Test early exit threshold has correct range.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.early_exit_input.minimum() == 0.0
    assert scanner_tab.early_exit_input.maximum() == 1.0
    assert scanner_tab.early_exit_input.decimals() == 3


def test_scanner_tab_confidence_gap_range(scanner_tab: ScannerTab) -> None:
    """Test confidence gap has correct range.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.confidence_gap_input.minimum() == 0.0
    assert scanner_tab.confidence_gap_input.maximum() == 1.0
    assert scanner_tab.confidence_gap_input.decimals() == 3


def test_scanner_tab_browse_database(qtbot: Any, scanner_tab: ScannerTab) -> None:
    """Test browse database button.

    Args:
        qtbot: PyQt test fixture
        scanner_tab: ScannerTab instance
    """
    test_path = "/path/to/database.h5"

    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "HDF5 Files (*.h5)")

        scanner_tab.browse_database()

        assert scanner_tab.database_path_input.text() == test_path


def test_scanner_tab_browse_database_cancel(qtbot: Any, scanner_tab: ScannerTab) -> None:
    """Test browse database cancel.

    Args:
        qtbot: PyQt test fixture
        scanner_tab: ScannerTab instance
    """
    original_text = scanner_tab.database_path_input.text()

    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        scanner_tab.browse_database()

        assert scanner_tab.database_path_input.text() == original_text


def test_scanner_tab_browse_screenshots(qtbot: Any, scanner_tab: ScannerTab) -> None:
    """Test browse screenshots button.

    Args:
        qtbot: PyQt test fixture
        scanner_tab: ScannerTab instance
    """
    test_path = "/path/to/screenshots"

    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab.QFileDialog.getExistingDirectory"
    ) as mock_dialog:
        mock_dialog.return_value = test_path

        scanner_tab.browse_screenshots()

        assert scanner_tab.screenshots_folder_input.text() == test_path


def test_scanner_tab_browse_screenshots_cancel(qtbot: Any, scanner_tab: ScannerTab) -> None:
    """Test browse screenshots cancel.

    Args:
        qtbot: PyQt test fixture
        scanner_tab: ScannerTab instance
    """
    original_text = scanner_tab.screenshots_folder_input.text()

    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab.QFileDialog.getExistingDirectory"
    ) as mock_dialog:
        mock_dialog.return_value = ""

        scanner_tab.browse_screenshots()

        assert scanner_tab.screenshots_folder_input.text() == original_text


def test_scanner_tab_set_values(scanner_tab: ScannerTab) -> None:
    """Test setting values from settings object.

    Args:
        scanner_tab: ScannerTab instance
    """
    settings = ScannerSettings(
        database_path=Path("/test/db.h5"),
        template_cache_size=8,
        early_exit_threshold=0.99,
        confidence_gap=0.1,
        debug_mode=True,
        extract_icons=True,
        screenshots_folder="/test/screenshots",
    )

    scanner_tab.set_values(settings)

    assert scanner_tab.database_path_input.text() == "/test/db.h5"
    assert scanner_tab.cache_size_input.value() == 8
    assert scanner_tab.early_exit_input.value() == 0.99
    assert scanner_tab.confidence_gap_input.value() == 0.1
    assert scanner_tab.debug_mode_input.isChecked()
    assert scanner_tab.extract_icons_input.isChecked()
    assert scanner_tab.screenshots_folder_input.text() == "/test/screenshots"


def test_scanner_tab_set_values_no_database_path(scanner_tab: ScannerTab) -> None:
    """Test setting values with no database path.

    Args:
        scanner_tab: ScannerTab instance
    """
    settings = ScannerSettings(database_path=None)

    scanner_tab.set_values(settings)

    assert scanner_tab.database_path_input.text() == ""


def test_scanner_tab_set_values_no_screenshots_folder(scanner_tab: ScannerTab) -> None:
    """Test setting values with no screenshots folder.

    Args:
        scanner_tab: ScannerTab instance
    """
    settings = ScannerSettings(screenshots_folder="")

    scanner_tab.set_values(settings)

    assert scanner_tab.screenshots_folder_input.text() == ""


def test_scanner_tab_get_values(scanner_tab: ScannerTab) -> None:
    """Test getting values from widgets.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.database_path_input.setText("/path/to/db.h5")
    scanner_tab.cache_size_input.setValue(4)
    scanner_tab.early_exit_input.setValue(0.995)
    scanner_tab.confidence_gap_input.setValue(0.15)
    scanner_tab.debug_mode_input.setChecked(True)
    scanner_tab.extract_icons_input.setChecked(False)
    scanner_tab.screenshots_folder_input.setText("/my/screenshots")

    settings = scanner_tab.get_values()

    assert settings.database_path == Path("/path/to/db.h5")
    assert settings.template_cache_size == 4
    assert settings.early_exit_threshold == 0.995
    assert settings.confidence_gap == 0.15
    assert settings.debug_mode is True
    assert settings.extract_icons is False
    assert settings.screenshots_folder == "/my/screenshots"


def test_scanner_tab_get_values_empty_database_path(scanner_tab: ScannerTab) -> None:
    """Test getting values with empty database path.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.database_path_input.setText("")

    settings = scanner_tab.get_values()

    assert settings.database_path is None


def test_scanner_tab_get_values_empty_screenshots_folder(scanner_tab: ScannerTab) -> None:
    """Test getting values with empty screenshots folder.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.screenshots_folder_input.setText("")

    settings = scanner_tab.get_values()

    assert settings.screenshots_folder == ""


def test_scanner_tab_checkboxes(scanner_tab: ScannerTab) -> None:
    """Test checkboxes behavior.

    Args:
        scanner_tab: ScannerTab instance
    """
    # Test debug mode
    scanner_tab.debug_mode_input.setChecked(True)
    assert scanner_tab.debug_mode_input.isChecked()

    scanner_tab.debug_mode_input.setChecked(False)
    assert not scanner_tab.debug_mode_input.isChecked()

    # Test extract icons
    scanner_tab.extract_icons_input.setChecked(True)
    assert scanner_tab.extract_icons_input.isChecked()

    scanner_tab.extract_icons_input.setChecked(False)
    assert not scanner_tab.extract_icons_input.isChecked()


def test_scanner_tab_double_spin_box_step(scanner_tab: ScannerTab) -> None:
    """Test double spin box step size.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.early_exit_input.singleStep() == 0.01
    assert scanner_tab.confidence_gap_input.singleStep() == 0.01


def test_scanner_tab_min_cache_size_boundary(scanner_tab: ScannerTab) -> None:
    """Test cache size at minimum boundary.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.cache_size_input.setValue(0)

    settings = scanner_tab.get_values()

    assert settings.template_cache_size == 0


def test_scanner_tab_max_cache_size_boundary(scanner_tab: ScannerTab) -> None:
    """Test cache size at maximum boundary.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.cache_size_input.setValue(16)

    settings = scanner_tab.get_values()

    assert settings.template_cache_size == 16


def test_scanner_tab_early_exit_precision(scanner_tab: ScannerTab) -> None:
    """Test early exit threshold precision.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.early_exit_input.setValue(0.999)

    settings = scanner_tab.get_values()

    assert settings.early_exit_threshold == 0.999


def test_scanner_tab_confidence_gap_precision(scanner_tab: ScannerTab) -> None:
    """Test confidence gap precision.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.confidence_gap_input.setValue(0.123)

    settings = scanner_tab.get_values()

    assert settings.confidence_gap == 0.123


def test_scanner_tab_set_values_default_settings(scanner_tab: ScannerTab) -> None:
    """Test setting values with default settings object.

    Args:
        scanner_tab: ScannerTab instance
    """
    settings = ScannerSettings()

    scanner_tab.set_values(settings)

    assert scanner_tab.cache_size_input.value() == settings.template_cache_size
    assert scanner_tab.early_exit_input.value() == settings.early_exit_threshold
    assert scanner_tab.confidence_gap_input.value() == settings.confidence_gap


def test_scanner_tab_set_config_level_basic(scanner_tab: ScannerTab) -> None:
    """Test set_config_level with BASIC level hides advanced widgets.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.set_config_level(ConfigLevel.BASIC)

    # Advanced widgets should be hidden
    # Use isHidden() instead of isVisible() since parent widget is not shown
    assert scanner_tab._debug_label.isHidden()
    assert scanner_tab.debug_mode_input.isHidden()
    assert scanner_tab._extract_label.isHidden()
    assert scanner_tab.extract_icons_input.isHidden()


def test_scanner_tab_set_config_level_advanced(scanner_tab: ScannerTab) -> None:
    """Test set_config_level with ADVANCED level shows advanced widgets.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.set_config_level(ConfigLevel.ADVANCED)

    # Advanced widgets should be visible
    # Use isHidden() instead of isVisible() since parent widget is not shown
    assert not scanner_tab._debug_label.isHidden()
    assert not scanner_tab.debug_mode_input.isHidden()
    assert not scanner_tab._extract_label.isHidden()
    assert not scanner_tab.extract_icons_input.isHidden()


def test_scanner_tab_set_config_level_developer(scanner_tab: ScannerTab) -> None:
    """Test set_config_level with DEVELOPER level shows all widgets.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.set_config_level(ConfigLevel.DEVELOPER)

    # Advanced widgets should be visible
    # Use isHidden() instead of isVisible() since parent widget is not shown
    assert not scanner_tab._debug_label.isHidden()
    assert not scanner_tab.debug_mode_input.isHidden()
    assert not scanner_tab._extract_label.isHidden()
    assert not scanner_tab.extract_icons_input.isHidden()


def test_scanner_tab_config_level_transition(scanner_tab: ScannerTab) -> None:
    """Test transitioning between config levels.

    Args:
        scanner_tab: ScannerTab instance
    """
    # Use isHidden() instead of isVisible() since parent widget is not shown

    # Start with developer
    scanner_tab.set_config_level(ConfigLevel.DEVELOPER)
    assert not scanner_tab._debug_label.isHidden()

    # Transition to advanced
    scanner_tab.set_config_level(ConfigLevel.ADVANCED)
    assert not scanner_tab._debug_label.isHidden()

    # Transition to basic
    scanner_tab.set_config_level(ConfigLevel.BASIC)
    assert scanner_tab._debug_label.isHidden()

    # Back to developer
    scanner_tab.set_config_level(ConfigLevel.DEVELOPER)
    assert not scanner_tab._debug_label.isHidden()


def test_scanner_tab_capture_key_roundtrip(scanner_tab: ScannerTab) -> None:
    """The capture hotkey round-trips through set_values/get_values.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.set_values(ScannerSettings(capture_key="F9"))
    assert scanner_tab.capture_key_display.text() == "F9"
    assert scanner_tab.get_values().capture_key == "F9"


def test_scanner_tab_clear_capture_key(scanner_tab: ScannerTab) -> None:
    """Clearing the capture hotkey yields a None capture_key.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.set_values(ScannerSettings(capture_key="F9"))
    scanner_tab.clear_capture_key()
    assert scanner_tab.get_values().capture_key is None
