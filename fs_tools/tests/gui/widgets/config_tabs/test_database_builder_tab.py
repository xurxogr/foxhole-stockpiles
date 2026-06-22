"""Tests for DatabaseBuilderTab."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

from foxhole_stockpiles.core.settings.sections.database_builder import DatabaseBuilderSettings
from foxhole_stockpiles.i18n import t
from fs_tools.gui.widgets.config_tabs.database_builder_tab import DatabaseBuilderTab


@pytest.fixture
def database_builder_tab(qtbot: Any) -> DatabaseBuilderTab:
    """Create a DatabaseBuilderTab instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        DatabaseBuilderTab: Tab instance
    """
    tab = DatabaseBuilderTab()
    qtbot.addWidget(tab)
    return tab


# ===== Initialization Tests =====


def test_database_builder_tab_initialization(database_builder_tab: DatabaseBuilderTab) -> None:
    """Test DatabaseBuilderTab initialization.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Note: extractor_tool_input and converter_tool_input are now in ExternalToolsTab
    # Note: workers is no longer edited here; it is configured per-build.
    assert database_builder_tab.catalog_file_input is not None
    assert database_builder_tab.resolution_list is not None


def test_database_builder_tab_widget_count(database_builder_tab: DatabaseBuilderTab) -> None:
    """Test that all input widgets are created.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Should have "All Resolutions" + 16 individual resolutions
    assert database_builder_tab.resolution_list.count() == 17


def test_database_builder_tab_all_resolutions_item_exists(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test that "All Resolutions" item is first in the list.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    all_item = database_builder_tab.resolution_list.item(0)
    assert all_item is not None
    assert all_item.text() == t("database_builder_tab.all_resolutions")


def test_database_builder_tab_resolution_items_checkable(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test that all resolution items are checkable.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        assert item is not None
        assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable


def test_database_builder_tab_default_all_resolutions_checked(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test that all resolutions are checked by default.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        assert item is not None
        assert item.checkState() == Qt.CheckState.Checked


# ===== Browse Tests =====


# Note: browse_extractor_tool and browse_converter_tool tests removed -
# these methods are now in ExternalToolsTab


def test_database_builder_tab_browse_catalog_file(
    qtbot: Any, database_builder_tab: DatabaseBuilderTab
) -> None:
    """Test browse catalog file button.

    Args:
        qtbot: PyQt test fixture
        database_builder_tab: DatabaseBuilderTab instance
    """
    test_path = "C:\\foxhole\\catalog.json"

    with patch(
        "fs_tools.gui.widgets.config_tabs.database_builder_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "JSON Files (*.json)")

        database_builder_tab.browse_catalog_file()

        assert database_builder_tab.catalog_file_input.text() == test_path


# ===== Set/Get Values Tests =====


def test_database_builder_tab_set_values_all_fields(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test setting values from settings object with all fields.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Note: extractor_tool and converter_tool are now in ExternalToolsSettings
    settings = DatabaseBuilderSettings(
        catalog_file=Path("C:\\foxhole\\catalog.json"),
        target_resolutions=None,  # None means all
    )

    database_builder_tab.set_values(settings)

    assert database_builder_tab.catalog_file_input.text() == "C:\\foxhole\\catalog.json"


def test_database_builder_tab_set_values_specific_resolutions(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test setting values with specific target resolutions.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    target_resolutions = ["1080", "1440", "2160"]
    settings = DatabaseBuilderSettings(target_resolutions=target_resolutions)

    database_builder_tab.set_values(settings)

    # Check "All Resolutions" is unchecked
    all_item = database_builder_tab.resolution_list.item(0)
    assert all_item is not None
    assert all_item.checkState() == Qt.CheckState.Unchecked

    # Check only selected resolutions are checked
    for i in range(1, database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        assert item is not None
        if item.text() in target_resolutions:
            assert item.checkState() == Qt.CheckState.Checked
        else:
            assert item.checkState() == Qt.CheckState.Unchecked


def test_database_builder_tab_get_values_all_fields_set(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test getting values with all fields set.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Note: extractor_tool and converter_tool are now in ExternalToolsTab
    database_builder_tab.catalog_file_input.setText("C:\\foxhole\\catalog.json")

    settings = database_builder_tab.get_values()

    assert settings.catalog_file == Path("C:\\foxhole\\catalog.json")


def test_database_builder_tab_get_values_empty_fields(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test getting values with empty fields.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Note: extractor_tool and converter_tool are now in ExternalToolsTab
    database_builder_tab.catalog_file_input.setText("")

    settings = database_builder_tab.get_values()

    assert settings.catalog_file is None


def test_database_builder_tab_get_values_all_resolutions_checked(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test getting values when all resolutions are checked.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # All should be checked by default
    settings = database_builder_tab.get_values()

    # When all are checked, should return None (meaning all)
    assert settings.target_resolutions is None


def test_database_builder_tab_roundtrip_specific_resolutions(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test set_values and get_values roundtrip with specific resolutions.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Note: extractor_tool and converter_tool are now in ExternalToolsTab
    target_resolutions = ["720", "1080", "1440"]
    original_settings = DatabaseBuilderSettings(
        catalog_file=Path("/data/catalog.json"),
        target_resolutions=target_resolutions,
    )

    database_builder_tab.set_values(original_settings)
    retrieved_settings = database_builder_tab.get_values()

    assert retrieved_settings.catalog_file == original_settings.catalog_file
    # Should match the original list
    assert set(retrieved_settings.target_resolutions or []) == set(target_resolutions)


# ===== Resolution Selection Handler Tests =====


def test_database_builder_tab_check_all_resolutions(
    qtbot: Any, database_builder_tab: DatabaseBuilderTab
) -> None:
    """Test checking 'All Resolutions' checkbox checks all individual resolutions.

    Args:
        qtbot: PyQt test fixture
        database_builder_tab: DatabaseBuilderTab instance
    """
    # First uncheck everything
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        if item:
            item.setCheckState(Qt.CheckState.Unchecked)

    # Now check the "All Resolutions" item (index 0)
    all_item = database_builder_tab.resolution_list.item(0)
    assert all_item is not None

    # Simulate user clicking the checkbox
    all_item.setCheckState(Qt.CheckState.Checked)

    # Wait for signal processing
    qtbot.wait(10)

    # All items should now be checked
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        assert item is not None
        assert item.checkState() == Qt.CheckState.Checked


def test_database_builder_tab_uncheck_all_resolutions(
    qtbot: Any, database_builder_tab: DatabaseBuilderTab
) -> None:
    """Test unchecking 'All Resolutions' checkbox unchecks all individual resolutions.

    Args:
        qtbot: PyQt test fixture
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Start with everything checked (default state)
    all_item = database_builder_tab.resolution_list.item(0)
    assert all_item is not None
    assert all_item.checkState() == Qt.CheckState.Checked

    # Simulate user unchecking the "All Resolutions" item
    all_item.setCheckState(Qt.CheckState.Unchecked)

    # Wait for signal processing
    qtbot.wait(10)

    # All items should now be unchecked
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        assert item is not None
        assert item.checkState() == Qt.CheckState.Unchecked


def test_database_builder_tab_check_individual_updates_all(
    qtbot: Any, database_builder_tab: DatabaseBuilderTab
) -> None:
    """Test checking individual resolutions updates 'All Resolutions' checkbox.

    Args:
        qtbot: PyQt test fixture
        database_builder_tab: DatabaseBuilderTab instance
    """
    # First uncheck everything
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        if item:
            item.setCheckState(Qt.CheckState.Unchecked)

    qtbot.wait(10)

    # Check all individual resolutions one by one
    for i in range(1, database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        if item:
            item.setCheckState(Qt.CheckState.Checked)
            qtbot.wait(10)

    # "All Resolutions" should now be checked automatically
    all_item = database_builder_tab.resolution_list.item(0)
    assert all_item is not None
    assert all_item.checkState() == Qt.CheckState.Checked


def test_database_builder_tab_uncheck_individual_updates_all(
    qtbot: Any, database_builder_tab: DatabaseBuilderTab
) -> None:
    """Test unchecking an individual resolution unchecks 'All Resolutions'.

    Args:
        qtbot: PyQt test fixture
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Start with everything checked (default state)
    all_item = database_builder_tab.resolution_list.item(0)
    assert all_item is not None
    assert all_item.checkState() == Qt.CheckState.Checked

    # Uncheck one individual resolution
    individual_item = database_builder_tab.resolution_list.item(1)
    assert individual_item is not None
    individual_item.setCheckState(Qt.CheckState.Unchecked)

    # Wait for signal processing
    qtbot.wait(10)

    # "All Resolutions" should now be unchecked
    assert all_item.checkState() == Qt.CheckState.Unchecked


def test_database_builder_tab_set_values_empty_list(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test set_values with empty target_resolutions list.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    settings = DatabaseBuilderSettings(target_resolutions=[])

    database_builder_tab.set_values(settings)

    # All items should be unchecked
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        assert item is not None
        assert item.checkState() == Qt.CheckState.Unchecked


def test_database_builder_tab_get_values_no_selections(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test get_values when no resolutions are selected.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Uncheck all items
    for i in range(database_builder_tab.resolution_list.count()):
        item = database_builder_tab.resolution_list.item(i)
        if item:
            item.setCheckState(Qt.CheckState.Unchecked)

    settings = database_builder_tab.get_values()

    # Should return empty list
    assert settings.target_resolutions == []


def test_database_builder_tab_handle_invalid_item(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test _handle_resolution_selection with invalid item.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    # Call with an object that doesn't have required attributes
    # Should return early without error
    database_builder_tab._handle_resolution_selection(object())


def test_database_builder_tab_set_values_on_fresh_instance(qtbot: Any) -> None:
    """Test set_values on a fresh tab instance (before signals are connected).

    Args:
        qtbot: PyQt test fixture
    """
    # Create a new tab instance
    tab = DatabaseBuilderTab()
    qtbot.addWidget(tab)

    # Manually disconnect the signal to simulate a fresh state
    # This exercises the TypeError exception handler in set_values
    try:
        tab.resolution_list.itemChanged.disconnect(tab._handle_resolution_selection)
    except TypeError:
        pass  # Already disconnected or never connected

    # Now call set_values - should handle the exception gracefully
    settings = DatabaseBuilderSettings(target_resolutions=["1080", "1440"])
    tab.set_values(settings)

    # Verify it worked
    retrieved = tab.get_values()
    assert set(retrieved.target_resolutions or []) == {"1080", "1440"}


# ===== Workers Tests =====
# Workers is no longer edited in this tab (it is configured per-build in the
# build-database window and via the CLI). The tab must preserve whatever value
# was loaded so that saving the general config never wipes it.


def test_database_builder_tab_workers_default_none(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test that the carried-through workers value defaults to None.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    assert database_builder_tab.get_values().workers is None


def test_database_builder_tab_preserves_workers_value(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test that a configured workers value survives a load/save round-trip.

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    database_builder_tab.set_values(DatabaseBuilderSettings(workers=4))
    assert database_builder_tab.get_values().workers == 4


def test_database_builder_tab_preserves_workers_none(
    database_builder_tab: DatabaseBuilderTab,
) -> None:
    """Test that a None workers value is preserved (not coerced).

    Args:
        database_builder_tab: DatabaseBuilderTab instance
    """
    database_builder_tab.set_values(DatabaseBuilderSettings(workers=None))
    assert database_builder_tab.get_values().workers is None
