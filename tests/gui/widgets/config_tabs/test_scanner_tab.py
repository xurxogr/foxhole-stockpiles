"""Tests for ScannerTab."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
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
    assert scanner_tab.capture_key_display is not None
    assert scanner_tab.early_exit_input is not None
    assert scanner_tab.confidence_gap_input is not None
    assert scanner_tab.screenshots_folder_input is not None


def test_scanner_tab_early_exit_range(scanner_tab: ScannerTab) -> None:
    """Test early exit threshold has correct range.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.early_exit_input.minimum() == 0.0
    assert scanner_tab.early_exit_input.maximum() == 1.0
    assert scanner_tab.early_exit_input.decimals() == 3


def test_scanner_tab_default_values(scanner_tab: ScannerTab) -> None:
    """Test default values are set correctly.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.confidence_gap_input.value() == 0.0


def test_scanner_tab_download_button_visible_only_when_db_unset(
    scanner_tab: ScannerTab,
) -> None:
    """The DB download button shows when no database path is set and hides when one is.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.set_values(ScannerSettings(database_path=None))
    assert not scanner_tab.db_download.isHidden()

    scanner_tab.set_values(ScannerSettings(database_path=Path("/tmp/db.h5")))
    assert scanner_tab.db_download.isHidden()


def test_scanner_tab_confidence_gap_range(scanner_tab: ScannerTab) -> None:
    """Test confidence gap has correct range.

    Args:
        scanner_tab: ScannerTab instance
    """
    assert scanner_tab.confidence_gap_input.minimum() == 0.0
    assert scanner_tab.confidence_gap_input.maximum() == 1.0
    assert scanner_tab.confidence_gap_input.decimals() == 3
    assert scanner_tab.confidence_gap_input.singleStep() == 0.01


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
    """Test browse screenshots folder button.

    Args:
        qtbot: PyQt test fixture
        scanner_tab: ScannerTab instance
    """
    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab.QFileDialog.getExistingDirectory"
    ) as mock_dialog:
        mock_dialog.return_value = "/path/to/screenshots"

        scanner_tab.browse_screenshots()

        assert scanner_tab.screenshots_folder_input.text() == "/path/to/screenshots"


def test_scanner_tab_browse_screenshots_cancel(qtbot: Any, scanner_tab: ScannerTab) -> None:
    """Test browse screenshots cancel keeps the existing value.

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
        capture_key="F9",
        early_exit_threshold=0.99,
        confidence_gap=0.1,
        screenshots_folder="/test/screenshots",
    )

    scanner_tab.set_values(settings)

    assert scanner_tab.database_path_input.text() == "/test/db.h5"
    assert scanner_tab.capture_key_display.text() == "F9"
    assert scanner_tab.early_exit_input.value() == 0.99
    assert scanner_tab.confidence_gap_input.value() == 0.1
    assert scanner_tab.screenshots_folder_input.text() == "/test/screenshots"


def test_scanner_tab_set_values_no_database_path(scanner_tab: ScannerTab) -> None:
    """Test setting values with no database path.

    Args:
        scanner_tab: ScannerTab instance
    """
    settings = ScannerSettings(database_path=None)

    scanner_tab.set_values(settings)

    assert scanner_tab.database_path_input.text() == ""


def test_scanner_tab_get_values(scanner_tab: ScannerTab) -> None:
    """Test getting values from widgets.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.database_path_input.setText("/path/to/db.h5")
    scanner_tab.early_exit_input.setValue(0.995)
    scanner_tab.confidence_gap_input.setValue(0.15)
    scanner_tab.screenshots_folder_input.setText("/my/screenshots")

    settings = scanner_tab.get_values()

    assert settings.database_path == Path("/path/to/db.h5")
    assert settings.early_exit_threshold == 0.995
    assert settings.confidence_gap == 0.15
    assert settings.screenshots_folder == "/my/screenshots"


def test_scanner_tab_get_values_empty_database_path(scanner_tab: ScannerTab) -> None:
    """Test getting values with empty database path.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.database_path_input.setText("")

    settings = scanner_tab.get_values()

    assert settings.database_path is None


def test_scanner_tab_confidence_gap_precision(scanner_tab: ScannerTab) -> None:
    """Test confidence gap precision.

    Args:
        scanner_tab: ScannerTab instance
    """
    scanner_tab.confidence_gap_input.setValue(0.123)

    settings = scanner_tab.get_values()

    assert settings.confidence_gap == 0.123


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
