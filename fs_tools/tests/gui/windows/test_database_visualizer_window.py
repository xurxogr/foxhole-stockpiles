"""Tests for DatabaseVisualizerWindow."""

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.icon_template import IconTemplate
from fs_tools.gui.windows.database_visualizer_window import (
    DatabaseLoader,
    DatabaseVisualizerWindow,
)
from fs_tools.template_db.template_database import TemplateDatabase


@pytest.fixture
def mock_template() -> IconTemplate:
    """Create a mock template for testing.

    Returns:
        IconTemplate: A mock template instance.
    """
    return IconTemplate(
        code="TestItem",
        faction=ItemFaction.NEUTRAL,
        category=ItemCategory.Item,
        mod="vanilla",
        crated=False,
        resolution=SupportedResolution.R_1080,
        image=np.zeros((32, 32, 3), dtype=np.uint8),
        phash=0,
    )


@pytest.fixture
def mock_crated_template() -> IconTemplate:
    """Create a mock crated template for testing.

    Returns:
        IconTemplate: A mock crated template instance.
    """
    return IconTemplate(
        code="TestItem",
        faction=ItemFaction.COLONIALS,
        category=ItemCategory.Vehicle,
        mod="testmod",
        crated=True,
        resolution=SupportedResolution.R_1080,
        image=np.zeros((32, 32, 3), dtype=np.uint8),
        phash=0,
    )


@pytest.fixture
def mock_database(mock_template: IconTemplate, mock_crated_template: IconTemplate) -> MagicMock:
    """Create a mock template database.

    Args:
        mock_template: Mock template fixture.
        mock_crated_template: Mock crated template fixture.

    Returns:
        MagicMock: A mock database instance.
    """
    db = MagicMock(spec=TemplateDatabase)
    db.templates = [mock_template, mock_crated_template]
    return db


@pytest.fixture
def visualizer_window(qtbot: Any) -> DatabaseVisualizerWindow:
    """Create a DatabaseVisualizerWindow instance without loading.

    Args:
        qtbot: PyQt test fixture.

    Returns:
        DatabaseVisualizerWindow: Window instance.
    """
    window = DatabaseVisualizerWindow(parent=None, database_path=None)
    qtbot.addWidget(window)
    return window


class TestDatabaseLoader:
    """Tests for DatabaseLoader thread."""

    def test_initialization(self) -> None:
        """Test DatabaseLoader initialization."""
        loader = DatabaseLoader("/path/to/db.h5")
        assert loader.database_path == "/path/to/db.h5"

    def test_run_success(self, qtbot: Any) -> None:
        """Test successful database loading.

        Args:
            qtbot: PyQt test fixture.
        """
        loader = DatabaseLoader("/path/to/db.h5")

        mock_databases = {SupportedResolution.R_1080: MagicMock()}

        with patch("fs_tools.gui.windows.database_visualizer_window.TemplateManager"):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.asyncio.run",
                return_value=mock_databases,
            ):
                # Connect signal to capture result
                result = []
                loader.finished.connect(lambda x: result.append(x))

                loader.run()

                assert len(result) == 1
                assert result[0] == mock_databases

    def test_run_error(self, qtbot: Any) -> None:
        """Test database loading error handling.

        Args:
            qtbot: PyQt test fixture.
        """
        loader = DatabaseLoader("/path/to/db.h5")

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.TemplateManager",
            side_effect=FileNotFoundError("Database not found"),
        ):
            # Connect signal to capture error
            errors = []
            loader.error.connect(lambda x: errors.append(x))

            loader.run()

            assert len(errors) == 1
            assert "Database not found" in errors[0]


class TestDatabaseVisualizerWindowInitialization:
    """Tests for DatabaseVisualizerWindow initialization."""

    def test_initialization_without_path(self, qtbot: Any) -> None:
        """Test window initialization without database path.

        Args:
            qtbot: PyQt test fixture.
        """
        window = DatabaseVisualizerWindow(parent=None, database_path=None)
        qtbot.addWidget(window)

        assert window.database_path is None
        assert window.all_databases == {}
        assert window.current_resolution is None
        assert window.database is None
        assert window.filtered_templates == []
        assert window.all_templates == []

    def test_initialization_with_path(self, qtbot: Any) -> None:
        """Test window initialization with database path starts loading.

        Args:
            qtbot: PyQt test fixture.
        """
        with patch.object(DatabaseVisualizerWindow, "load_databases") as mock_load:
            window = DatabaseVisualizerWindow(parent=None, database_path="/path/to/db.h5")
            qtbot.addWidget(window)

            assert window.database_path == "/path/to/db.h5"
            mock_load.assert_called_once()

    def test_window_title(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test initial window title.

        Args:
            visualizer_window: Window fixture.
        """
        assert t("database_visualizer.title") in visualizer_window.windowTitle()

    def test_minimum_size(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test window minimum size.

        Args:
            visualizer_window: Window fixture.
        """
        assert visualizer_window.minimumWidth() >= 1200
        assert visualizer_window.minimumHeight() >= 700


class TestDatabaseVisualizerWindowUI:
    """Tests for DatabaseVisualizerWindow UI components."""

    def test_filter_widgets_exist(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test that filter widgets are created.

        Args:
            visualizer_window: Window fixture.
        """
        assert visualizer_window.resolution_filter is not None
        assert visualizer_window.code_filter is not None
        assert visualizer_window.faction_filter is not None
        assert visualizer_window.category_filter is not None
        assert visualizer_window.mod_filter is not None
        assert visualizer_window.crated_all is not None
        assert visualizer_window.crated_normal is not None
        assert visualizer_window.crated_crated is not None

    def test_image_labels_exist(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test that image display labels are created.

        Args:
            visualizer_window: Window fixture.
        """
        assert visualizer_window.current_image is not None
        assert visualizer_window.highest_image is not None
        assert visualizer_window.info_label_left is not None
        assert visualizer_window.info_label_right is not None

    def test_progress_bar_hidden_initially(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that progress bar is hidden initially.

        Args:
            visualizer_window: Window fixture.
        """
        assert not visualizer_window.progress_bar.isVisible()

    def test_faction_filter_options(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test faction filter has all options.

        Args:
            visualizer_window: Window fixture.
        """
        # Should have "All" plus all factions
        assert visualizer_window.faction_filter.count() >= len(ItemFaction) + 1
        assert visualizer_window.faction_filter.itemText(0) == t("common.all")

    def test_category_filter_options(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test category filter has all options.

        Args:
            visualizer_window: Window fixture.
        """
        # Should have "All" plus all categories
        assert visualizer_window.category_filter.count() >= len(ItemCategory) + 1
        assert visualizer_window.category_filter.itemText(0) == t("common.all")

    def test_crated_all_checked_initially(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test crated 'All' checkbox is checked initially.

        Args:
            visualizer_window: Window fixture.
        """
        assert visualizer_window.crated_all.isChecked()
        assert not visualizer_window.crated_normal.isChecked()
        assert not visualizer_window.crated_crated.isChecked()


class TestDatabaseVisualizerWindowFilters:
    """Tests for filter functionality."""

    def test_clear_filters(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test clearing all filters.

        Args:
            visualizer_window: Window fixture.
        """
        # Set some filter values
        visualizer_window.code_filter.setText("test")
        visualizer_window.faction_filter.setCurrentIndex(1)
        visualizer_window.crated_all.setChecked(False)
        visualizer_window.crated_normal.setChecked(True)

        # Clear filters
        visualizer_window._clear_filters()

        # Verify all reset
        assert visualizer_window.code_filter.text() == ""
        assert visualizer_window.faction_filter.currentIndex() == 0
        assert visualizer_window.crated_all.isChecked()
        assert not visualizer_window.crated_normal.isChecked()
        assert not visualizer_window.crated_crated.isChecked()

    def test_crated_all_toggle_unchecks_others(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that checking 'All' unchecks normal and crated.

        Args:
            visualizer_window: Window fixture.
        """
        # First uncheck All and check others
        visualizer_window.crated_all.setChecked(False)
        visualizer_window.crated_normal.setChecked(True)
        visualizer_window.crated_crated.setChecked(True)

        # Now check All
        visualizer_window.crated_all.setChecked(True)

        # Others should be unchecked
        assert not visualizer_window.crated_normal.isChecked()
        assert not visualizer_window.crated_crated.isChecked()

    def test_apply_filters_no_database(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test apply filters does nothing without database.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.database = None
        visualizer_window._apply_filters()
        # Should not raise, just return early

    def test_apply_filters_code_filter(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_crated_template: IconTemplate,
    ) -> None:
        """Test code filter functionality.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
            mock_crated_template: Mock crated template.
        """
        visualizer_window.database = MagicMock()
        visualizer_window.all_templates = [(0, mock_template), (1, mock_crated_template)]

        # Filter by code
        visualizer_window.code_filter.setText("TestItem")
        visualizer_window._apply_filters()

        # Both should match
        assert len(visualizer_window.filtered_templates) == 2

        # Filter by non-existing code
        visualizer_window.code_filter.setText("NonExistent")
        visualizer_window._apply_filters()

        assert len(visualizer_window.filtered_templates) == 0

    def test_apply_filters_faction_filter(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_crated_template: IconTemplate,
    ) -> None:
        """Test faction filter functionality.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template (NEUTRAL).
            mock_crated_template: Mock crated template (COLONIALS).
        """
        visualizer_window.database = MagicMock()
        visualizer_window.all_templates = [(0, mock_template), (1, mock_crated_template)]

        # Filter by COLONIALS
        visualizer_window.faction_filter.setCurrentIndex(
            visualizer_window.faction_filter.findData(ItemFaction.COLONIALS)
        )
        visualizer_window._apply_filters()

        # Only crated template should match
        assert len(visualizer_window.filtered_templates) == 1
        assert visualizer_window.filtered_templates[0][1].faction == ItemFaction.COLONIALS

    def test_apply_filters_crated_filter(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_crated_template: IconTemplate,
    ) -> None:
        """Test crated filter functionality.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template (not crated).
            mock_crated_template: Mock crated template.
        """
        visualizer_window.database = MagicMock()
        visualizer_window.all_templates = [(0, mock_template), (1, mock_crated_template)]

        # Show only crated
        visualizer_window.crated_all.setChecked(False)
        visualizer_window.crated_crated.setChecked(True)
        visualizer_window._apply_filters()

        assert len(visualizer_window.filtered_templates) == 1
        assert visualizer_window.filtered_templates[0][1].crated is True

        # Show only normal
        visualizer_window.crated_crated.setChecked(False)
        visualizer_window.crated_normal.setChecked(True)
        visualizer_window._apply_filters()

        assert len(visualizer_window.filtered_templates) == 1
        assert visualizer_window.filtered_templates[0][1].crated is False


class TestDatabaseVisualizerWindowDatabaseLoading:
    """Tests for database loading functionality."""

    def test_load_databases_no_path(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test load_databases with no path shows message.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.database_path = None
        visualizer_window.load_databases()

        assert t("database_visualizer.no_database_path") in visualizer_window.results_label.text()

    def test_load_databases_starts_thread(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test load_databases starts loader thread.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.database_path = "/path/to/db.h5"

        with patch.object(DatabaseLoader, "start") as mock_start:
            visualizer_window.load_databases()

            assert visualizer_window.loader_thread is not None
            # Progress bar should be visible after load_databases is called
            # (check the property was set, not visibility which requires event processing)
            assert visualizer_window.results_label.text() == t(
                "database_visualizer.loading_databases"
            )
            mock_start.assert_called_once()

    def test_on_databases_loaded(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_database: MagicMock,
    ) -> None:
        """Test successful database load handling.

        Args:
            visualizer_window: Window fixture.
            mock_database: Mock database.
        """
        all_databases: Any = {
            SupportedResolution.R_1080: mock_database,
            SupportedResolution.R_1440: mock_database,
        }

        visualizer_window.progress_bar.setVisible(True)
        visualizer_window._on_databases_loaded(all_databases)

        # Progress bar should be hidden
        assert not visualizer_window.progress_bar.isVisible()

        # Resolution filter should be populated
        assert visualizer_window.resolution_filter.count() == 2

        # Databases should be stored
        assert visualizer_window.all_databases == all_databases

    def test_on_database_error(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test database error handling.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.progress_bar.setVisible(True)
        visualizer_window._on_database_error("Test error message")

        assert not visualizer_window.progress_bar.isVisible()
        # The error message should contain the translated error prefix
        error_text = visualizer_window.results_label.text()
        assert "Test error message" in error_text


class TestDatabaseVisualizerWindowResolutionChange:
    """Tests for resolution change handling."""

    def test_on_resolution_changed(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_database: MagicMock,
        mock_template: IconTemplate,
    ) -> None:
        """Test resolution change updates database and filters.

        Args:
            visualizer_window: Window fixture.
            mock_database: Mock database.
            mock_template: Mock template.
        """
        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_database}

        # Add resolution to filter
        visualizer_window.resolution_filter.clear()
        visualizer_window.resolution_filter.addItem("1080p", SupportedResolution.R_1080)
        visualizer_window.resolution_filter.setCurrentIndex(0)

        # Trigger resolution change
        visualizer_window._on_resolution_changed()

        assert visualizer_window.current_resolution == SupportedResolution.R_1080
        assert visualizer_window.database == mock_database
        assert "1080p" in visualizer_window.windowTitle()


class TestDatabaseVisualizerWindowTemplateSelection:
    """Tests for template selection."""

    def test_update_template_list(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_crated_template: IconTemplate,
    ) -> None:
        """Test template list update.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
            mock_crated_template: Mock crated template.
        """
        visualizer_window.all_templates = [(0, mock_template), (1, mock_crated_template)]
        visualizer_window.filtered_templates = [(0, mock_template), (1, mock_crated_template)]

        visualizer_window._update_template_list()

        assert visualizer_window.template_list.count() == 2
        # Check that the result label shows the count (format varies by language)
        assert "2" in visualizer_window.results_label.text()

    def test_on_template_selected(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_database: MagicMock,
    ) -> None:
        """Test template selection updates info label.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
            mock_database: Mock database.
        """
        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_database}

        # Create list item with template data
        item = QListWidgetItem("TestItem")
        item.setData(Qt.ItemDataRole.UserRole, (0, mock_template))

        visualizer_window._on_template_selected(item)

        # Info labels should contain template details
        info_text_left = visualizer_window.info_label_left.text()
        assert "TestItem" in info_text_left
        assert "neutral" in info_text_left
        assert "vanilla" in info_text_left


class TestDatabaseVisualizerWindowFiltersAdvanced:
    """Additional tests for filter edge cases."""

    def test_apply_filters_category_filter(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_crated_template: IconTemplate,
    ) -> None:
        """Test category filter functionality.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template (Item category).
            mock_crated_template: Mock crated template (Vehicle category).
        """
        visualizer_window.database = MagicMock()
        visualizer_window.all_templates = [(0, mock_template), (1, mock_crated_template)]

        # Filter by Vehicle category
        visualizer_window.category_filter.setCurrentIndex(
            visualizer_window.category_filter.findData(ItemCategory.Vehicle)
        )
        visualizer_window._apply_filters()

        # Only crated template (Vehicle) should match
        assert len(visualizer_window.filtered_templates) == 1
        assert visualizer_window.filtered_templates[0][1].category == ItemCategory.Vehicle

    def test_apply_filters_mod_filter(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_crated_template: IconTemplate,
    ) -> None:
        """Test mod filter functionality.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template (vanilla mod).
            mock_crated_template: Mock crated template (testmod mod).
        """
        visualizer_window.database = MagicMock()
        visualizer_window.all_templates = [(0, mock_template), (1, mock_crated_template)]

        # Add mods to filter
        visualizer_window.mod_filter.clear()
        visualizer_window.mod_filter.addItem("All", "")
        visualizer_window.mod_filter.addItem("vanilla", "vanilla")
        visualizer_window.mod_filter.addItem("testmod", "testmod")

        # Filter by testmod
        visualizer_window.mod_filter.setCurrentIndex(
            visualizer_window.mod_filter.findData("testmod")
        )
        visualizer_window._apply_filters()

        # Only crated template (testmod) should match
        assert len(visualizer_window.filtered_templates) == 1
        assert visualizer_window.filtered_templates[0][1].mod == "testmod"

    def test_on_resolution_changed_restores_mod_selection(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_database: MagicMock,
        mock_template: IconTemplate,
    ) -> None:
        """Test resolution change restores mod selection if available.

        Args:
            visualizer_window: Window fixture.
            mock_database: Mock database.
            mock_template: Mock template.
        """
        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_database}

        # Set up mod filter with a selection
        visualizer_window.mod_filter.clear()
        visualizer_window.mod_filter.addItem("All", "")
        visualizer_window.mod_filter.addItem("vanilla", "vanilla")
        visualizer_window.mod_filter.setCurrentIndex(1)  # Select "vanilla"

        # Add resolution to filter
        visualizer_window.resolution_filter.clear()
        visualizer_window.resolution_filter.addItem("1080p", SupportedResolution.R_1080)
        visualizer_window.resolution_filter.setCurrentIndex(0)

        # Trigger resolution change - should restore mod selection
        visualizer_window._on_resolution_changed()

        # Mod filter should have "vanilla" selected if it exists
        assert visualizer_window.mod_filter.currentData() == "vanilla"


class TestDatabaseVisualizerWindowTemplateSelectionAdvanced:
    """Additional tests for template selection edge cases."""

    def test_on_template_selected_highest_not_found(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test template selection when highest resolution template not found.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        # Create a database with different template (won't match)
        different_template = IconTemplate(
            code="DifferentItem",
            faction=ItemFaction.WARDENS,
            category=ItemCategory.Shippable,
            mod="othermod",
            crated=True,
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        mock_db = MagicMock(spec=TemplateDatabase)
        mock_db.templates = [different_template]

        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_db}

        # Create list item with template data
        item = QListWidgetItem("TestItem")
        item.setData(Qt.ItemDataRole.UserRole, (0, mock_template))

        visualizer_window._on_template_selected(item)

        # Right info label should indicate highest resolution not found
        info_text_right = visualizer_window.info_label_right.text()
        # Check for the resolution (1080px) in the not found message
        assert "1080" in info_text_right


class TestDatabaseVisualizerWindowImageDisplay:
    """Tests for image display functionality."""

    def test_display_comparison_images_no_template(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test display does nothing with no template.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window._display_comparison_images(None, None)
        # Should not raise

    def test_display_comparison_images_with_template(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test display with template shows image.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        # Create a non-zero image for display
        mock_template.image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        visualizer_window._display_comparison_images(mock_template, None)

        # Current image should have a pixmap
        assert not visualizer_window.current_image.pixmap().isNull()

        # Highest should show not found text (check translation key)
        assert t("database_visualizer.template_not_found") in visualizer_window.highest_image.text()

    def test_display_comparison_images_with_both(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test display with both templates shows comparison.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        # Create images
        mock_template.image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        highest_template = IconTemplate(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            mod="vanilla",
            crated=False,
            resolution=SupportedResolution.R_1440,
            image=np.ones((48, 48, 3), dtype=np.uint8) * 200,
            phash=0,
        )

        visualizer_window._display_comparison_images(mock_template, highest_template)

        # Both images should have pixmaps
        assert not visualizer_window.current_image.pixmap().isNull()
        assert not visualizer_window.highest_image.pixmap().isNull()


class TestDatabaseVisualizerWindowReplaceIcon:
    """Tests for replace icon functionality."""

    def test_replace_button_disabled_initially(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that replace button is disabled on init.

        Args:
            visualizer_window: Window fixture.
        """
        assert not visualizer_window.replace_button.isEnabled()
        assert visualizer_window.selected_template is None

    def test_template_selection_enables_replace_button(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_database: MagicMock,
    ) -> None:
        """Test selecting a template enables replace button.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
            mock_database: Mock database.
        """
        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_database}

        item = QListWidgetItem("TestItem")
        item.setData(Qt.ItemDataRole.UserRole, (0, mock_template))

        visualizer_window._on_template_selected(item)

        assert visualizer_window.replace_button.isEnabled()
        assert visualizer_window.selected_template == (0, mock_template)

    def test_resolution_change_clears_selection(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
        mock_database: MagicMock,
    ) -> None:
        """Test resolution change clears selected template.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
            mock_database: Mock database.
        """
        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_database}
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.replace_button.setEnabled(True)

        visualizer_window.resolution_filter.clear()
        visualizer_window.resolution_filter.addItem("1080p", SupportedResolution.R_1080)

        visualizer_window._on_resolution_changed()

        assert visualizer_window.selected_template is None
        assert not visualizer_window.replace_button.isEnabled()

    def test_replace_icon_no_selection_returns_early(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test replace icon does nothing without selection.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.selected_template = None

        with patch("fs_tools.gui.windows.database_visualizer_window.QFileDialog") as mock_dialog:
            visualizer_window._on_replace_icon()
            mock_dialog.getOpenFileName.assert_not_called()

    def test_replace_icon_cancelled_dialog_returns_early(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test replace icon returns early when dialog cancelled.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            with patch("fs_tools.gui.windows.database_visualizer_window.Image") as mock_image:
                visualizer_window._on_replace_icon()
                mock_image.open.assert_not_called()

    def test_replace_icon_image_load_error(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test replace icon handles image load error.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
            return_value=("/path/to/icon.png", "PNG Files (*.png)"),
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.Image.open",
                side_effect=FileNotFoundError("File not found"),
            ):
                with patch.object(visualizer_window, "_show_replace_error") as mock_show_error:
                    visualizer_window._on_replace_icon()
                    mock_show_error.assert_called_once()
                    assert "File not found" in mock_show_error.call_args[0][0]

    def test_replace_icon_success(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test successful icon replacement.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}

        # Create mock PIL image
        mock_pil_image = MagicMock()
        mock_pil_image.mode = "RGB"
        mock_pil_image.size = (32, 32)

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
                return_value=("/path/to/icon.png", "PNG Files (*.png)"),
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.Image.open",
                    return_value=mock_pil_image,
                ):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.np.array",
                        return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                    ):
                        with patch(
                            "fs_tools.gui.windows.database_visualizer_window.cv2.cvtColor",
                            return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                        ):
                            with patch(
                                "fs_tools.gui.windows.database_visualizer_window.IconManager"
                            ) as mock_manager_class:
                                with patch(
                                    "fs_tools.gui.windows.database_visualizer_window.TemplateManager.save_single_resolution"
                                ):
                                    with patch(
                                        "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                                    ):
                                        with patch.object(visualizer_window, "_apply_filters"):
                                            visualizer_window._on_replace_icon()

                                            mock_manager_class.assert_called_once()

    def test_replace_icon_rgba_image(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test icon replacement with RGBA image conversion.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}

        # Create mock PIL RGBA image
        mock_pil_image = MagicMock()
        mock_pil_image.mode = "RGBA"
        mock_pil_image.size = (32, 32)
        mock_pil_image.split.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

        mock_background = MagicMock()

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
                return_value=("/path/to/icon.png", ""),
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.Image.open",
                    return_value=mock_pil_image,
                ):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.Image.new",
                        return_value=mock_background,
                    ) as mock_new:
                        with patch(
                            "fs_tools.gui.windows.database_visualizer_window.np.array",
                            return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                        ):
                            with patch(
                                "fs_tools.gui.windows.database_visualizer_window.cv2.cvtColor",
                                return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                            ):
                                with patch(
                                    "fs_tools.gui.windows.database_visualizer_window.IconManager"
                                ):
                                    with patch(
                                        "fs_tools.gui.windows.database_visualizer_window.TemplateManager.save_single_resolution"
                                    ):
                                        with patch(
                                            "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                                        ):
                                            with patch.object(visualizer_window, "_apply_filters"):
                                                visualizer_window._on_replace_icon()
                                                # Verify RGBA conversion was used
                                                mock_new.assert_called_once()

    def test_replace_icon_palette_image(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test icon replacement with palette mode image conversion.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}

        # Create mock PIL palette image
        mock_pil_image = MagicMock()
        mock_pil_image.mode = "P"  # Palette mode
        mock_pil_image.size = (32, 32)
        mock_converted = MagicMock()
        mock_converted.size = (32, 32)
        mock_pil_image.convert.return_value = mock_converted

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
                return_value=("/path/to/icon.png", ""),
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.Image.open",
                    return_value=mock_pil_image,
                ):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.np.array",
                        return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                    ):
                        with patch(
                            "fs_tools.gui.windows.database_visualizer_window.cv2.cvtColor",
                            return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                        ):
                            with patch(
                                "fs_tools.gui.windows.database_visualizer_window.IconManager"
                            ):
                                with patch(
                                    "fs_tools.gui.windows.database_visualizer_window.TemplateManager.save_single_resolution"
                                ):
                                    with patch(
                                        "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                                    ):
                                        with patch.object(visualizer_window, "_apply_filters"):
                                            visualizer_window._on_replace_icon()
                                            # Verify convert was called
                                            mock_pil_image.convert.assert_called_with("RGB")

    def test_replace_icon_resize(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test icon replacement with image resize.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}

        # Create mock PIL image with wrong size
        mock_pil_image = MagicMock()
        mock_pil_image.mode = "RGB"
        mock_pil_image.size = (64, 64)  # Wrong size, needs resize

        mock_resized = MagicMock()
        mock_resized.size = (32, 32)
        mock_pil_image.resize.return_value = mock_resized

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
                return_value=("/path/to/icon.png", ""),
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.Image.open",
                    return_value=mock_pil_image,
                ):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.np.array",
                        return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                    ):
                        with patch(
                            "fs_tools.gui.windows.database_visualizer_window.cv2.cvtColor",
                            return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                        ):
                            with patch(
                                "fs_tools.gui.windows.database_visualizer_window.IconManager"
                            ):
                                with patch(
                                    "fs_tools.gui.windows.database_visualizer_window.TemplateManager.save_single_resolution"
                                ):
                                    with patch(
                                        "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                                    ):
                                        with patch.object(visualizer_window, "_apply_filters"):
                                            visualizer_window._on_replace_icon()
                                            # Verify resize was called
                                            mock_pil_image.resize.assert_called_once()

    def test_replace_icon_manager_error(
        self,
        visualizer_window: DatabaseVisualizerWindow,
        mock_template: IconTemplate,
    ) -> None:
        """Test icon replacement with IconManager error.

        Args:
            visualizer_window: Window fixture.
            mock_template: Mock template.
        """
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/path/to/db.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}

        mock_pil_image = MagicMock()
        mock_pil_image.mode = "RGB"
        mock_pil_image.size = (32, 32)

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
                return_value=("/path/to/icon.png", ""),
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.Image.open",
                    return_value=mock_pil_image,
                ):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.np.array",
                        return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                    ):
                        with patch(
                            "fs_tools.gui.windows.database_visualizer_window.cv2.cvtColor",
                            return_value=np.zeros((32, 32, 3), dtype=np.uint8),
                        ):
                            with patch(
                                "fs_tools.gui.windows.database_visualizer_window.IconManager",
                                side_effect=Exception("Manager error"),
                            ):
                                with patch.object(
                                    visualizer_window, "_show_replace_error"
                                ) as mock_error:
                                    visualizer_window._on_replace_icon()
                                    mock_error.assert_called_once()

    def test_show_replace_error(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test error display helper.

        Args:
            visualizer_window: Window fixture.
        """
        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QMessageBox.critical"
        ) as mock_critical:
            visualizer_window._show_replace_error("Test error")

            mock_critical.assert_called_once()
            call_args = mock_critical.call_args[0]
            assert "Test error" in call_args[2]


class TestDatabaseVisualizerWindowLanguageChange:
    """Tests for language change handling."""

    def test_on_language_changed(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test language change triggers retranslate.

        Args:
            visualizer_window: Window fixture.
        """
        with patch.object(visualizer_window, "retranslate") as mock_retranslate:
            visualizer_window._on_language_changed("es")
            mock_retranslate.assert_called_once()


class TestDatabaseVisualizerWindowSaveIcon:
    """Tests for save icon functionality."""

    def test_save_button_disabled_initially(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test save button is disabled when no template selected.

        Args:
            visualizer_window: Window fixture.
        """
        assert not visualizer_window.save_button.isEnabled()

    def test_save_icon_no_selection_returns_early(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test save icon returns early when no template selected.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.selected_template = None

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            visualizer_window._on_save_icon()
            mock_dialog.assert_not_called()

    def test_save_icon_cancelled_dialog_returns_early(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test save icon returns early when dialog cancelled.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        mock_template.resolution.value = "1080"
        visualizer_window.selected_template = (0, mock_template)

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            with patch("fs_tools.gui.windows.database_visualizer_window.cv2.imwrite") as mock_write:
                visualizer_window._on_save_icon()
                mock_write.assert_not_called()

    def test_save_icon_success(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test successful icon save.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        mock_template.crated = False
        mock_template.resolution.value = "1080"
        mock_template.image = np.zeros((32, 32, 3), dtype=np.uint8)
        visualizer_window.selected_template = (0, mock_template)

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getSaveFileName",
            return_value=("/tmp/test.png", ""),
        ) as mock_dialog:
            with patch("fs_tools.gui.windows.database_visualizer_window.cv2.imwrite") as mock_write:
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                ) as mock_info:
                    visualizer_window._on_save_icon()

                    # Verify default filename doesn't have _crated
                    call_args = mock_dialog.call_args
                    assert call_args[0][2] == "TestItem_1080p.png"

                    mock_write.assert_called_once()
                    mock_info.assert_called_once()

    def test_save_icon_crated_filename(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test save icon uses _crated suffix for crated items.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        mock_template.crated = True
        mock_template.resolution.value = "1080"
        mock_template.image = np.zeros((32, 32, 3), dtype=np.uint8)
        visualizer_window.selected_template = (0, mock_template)

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getSaveFileName",
            return_value=("/tmp/test.png", ""),
        ) as mock_dialog:
            with patch("fs_tools.gui.windows.database_visualizer_window.cv2.imwrite"):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                ):
                    visualizer_window._on_save_icon()

                    # Verify default filename has _crated suffix
                    call_args = mock_dialog.call_args
                    assert call_args[0][2] == "TestItem_crated_1080p.png"

    def test_save_icon_error(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test error handling when save fails.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        mock_template.resolution.value = "1080"
        mock_template.image = np.zeros((32, 32, 3), dtype=np.uint8)
        visualizer_window.selected_template = (0, mock_template)

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getSaveFileName",
            return_value=("/tmp/test.png", ""),
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.cv2.imwrite",
                side_effect=Exception("Write failed"),
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.QMessageBox.critical"
                ) as mock_critical:
                    visualizer_window._on_save_icon()
                    mock_critical.assert_called_once()


class TestDatabaseVisualizerWindowDeleteIcon:
    """Tests for delete icon functionality."""

    def test_delete_button_disabled_initially(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test delete button is disabled when no template selected.

        Args:
            visualizer_window: Window fixture.
        """
        assert not visualizer_window.delete_button.isEnabled()

    def test_delete_icon_no_selection_returns_early(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test delete icon returns early when no template selected.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.selected_template = None

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QMessageBox.question"
        ) as mock_dialog:
            visualizer_window._on_delete_icon()
            mock_dialog.assert_not_called()

    def test_delete_icon_cancelled_returns_early(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test delete icon returns early when user cancels confirmation.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/tmp/test.h5"

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.IconManager"
            ) as mock_manager:
                visualizer_window._on_delete_icon()
                mock_manager.assert_not_called()

    def test_delete_icon_success(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test successful icon delete.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/tmp/test.h5"
        mock_database = MagicMock()
        mock_database.templates = []
        visualizer_window.all_databases = {SupportedResolution.R_1080: mock_database}
        visualizer_window.database = mock_database

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                with patch("fs_tools.gui.windows.database_visualizer_window.IconManager"):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.TemplateManager.save_single_resolution"
                    ):
                        with patch(
                            "fs_tools.gui.windows.database_visualizer_window.QMessageBox.information"
                        ):
                            visualizer_window._on_delete_icon()

                            # Verify selection was cleared and buttons disabled
                            assert visualizer_window.selected_template is None
                            assert not visualizer_window.save_button.isEnabled()
                            assert not visualizer_window.replace_button.isEnabled()
                            assert not visualizer_window.delete_button.isEnabled()

    def test_delete_icon_error(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test error handling when delete fails.

        Args:
            visualizer_window: Window fixture.
        """
        mock_template = MagicMock()
        mock_template.code = "TestItem"
        visualizer_window.selected_template = (0, mock_template)
        visualizer_window.current_resolution = SupportedResolution.R_1080
        visualizer_window.database_path = "/tmp/test.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}

        # Mock OCRSettings to return proper OCR settings
        mock_settings = MagicMock()
        mock_settings.box_height = 64
        mock_settings.height = 2160

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.OCRSettings",
            return_value=mock_settings,
        ):
            with patch(
                "fs_tools.gui.windows.database_visualizer_window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                with patch(
                    "fs_tools.gui.windows.database_visualizer_window.IconManager",
                    side_effect=Exception("Delete failed"),
                ):
                    with patch(
                        "fs_tools.gui.windows.database_visualizer_window.QMessageBox.critical"
                    ) as mock_critical:
                        visualizer_window._on_delete_icon()
                        mock_critical.assert_called_once()


class TestDatabaseVisualizerWindowFilterPreservation:
    """Tests for filter state preservation during reload."""

    def test_get_current_filter_state(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test getting current filter state.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.code_filter.setText("TestCode")
        visualizer_window.crated_normal.setChecked(True)
        visualizer_window.crated_all.setChecked(False)

        state = visualizer_window._get_current_filter_state()

        assert state["code"] == "TestCode"
        assert state["crated_normal"] is True
        assert state["crated_all"] is False

    def test_restore_filter_state(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test restoring filter state.

        Args:
            visualizer_window: Window fixture.
        """
        state = {
            "resolution": None,
            "code": "RestoredCode",
            "faction": None,
            "category": None,
            "mod": None,
            "crated_all": False,
            "crated_normal": True,
            "crated_crated": False,
        }

        visualizer_window._restore_filter_state(state)  # type: ignore[arg-type]

        assert visualizer_window.code_filter.text() == "RestoredCode"
        assert visualizer_window.crated_normal.isChecked() is True
        assert visualizer_window.crated_all.isChecked() is False

    def test_restore_filter_state_with_all_filters(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test restoring filter state with all filter values set.

        Args:
            visualizer_window: Window fixture.
        """
        # First populate the combo boxes with data
        visualizer_window.resolution_filter.clear()
        visualizer_window.resolution_filter.addItem("1080p", SupportedResolution.R_1080)
        visualizer_window.resolution_filter.addItem("1440p", SupportedResolution.R_1440)

        # Mod filter needs items
        visualizer_window.mod_filter.clear()
        visualizer_window.mod_filter.addItem("All", "")
        visualizer_window.mod_filter.addItem("vanilla", "vanilla")
        visualizer_window.mod_filter.addItem("testmod", "testmod")

        state = {
            "resolution": SupportedResolution.R_1440,
            "code": "FilteredCode",
            "faction": ItemFaction.COLONIALS,
            "category": ItemCategory.Vehicle,
            "mod": "testmod",
            "crated_all": False,
            "crated_normal": False,
            "crated_crated": True,
        }

        visualizer_window._restore_filter_state(state)

        # Check resolution was restored
        assert visualizer_window.resolution_filter.currentData() == SupportedResolution.R_1440

        # Check code was restored
        assert visualizer_window.code_filter.text() == "FilteredCode"

        # Check faction was restored
        assert visualizer_window.faction_filter.currentData() == ItemFaction.COLONIALS

        # Check category was restored
        assert visualizer_window.category_filter.currentData() == ItemCategory.Vehicle

        # Check mod was restored
        assert visualizer_window.mod_filter.currentData() == "testmod"

        # Check crated was restored
        assert visualizer_window.crated_crated.isChecked() is True

    def test_reload_preserving_filters_clears_selection(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that reload clears selection and disables buttons.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.database_path = "/tmp/test.h5"
        visualizer_window.selected_template = (0, MagicMock())
        visualizer_window.save_button.setEnabled(True)
        visualizer_window.replace_button.setEnabled(True)
        visualizer_window.delete_button.setEnabled(True)

        with patch.object(visualizer_window, "load_databases"):
            visualizer_window._reload_preserving_filters()

        assert visualizer_window.selected_template is None
        assert not visualizer_window.save_button.isEnabled()
        assert not visualizer_window.replace_button.isEnabled()
        assert not visualizer_window.delete_button.isEnabled()

    def test_on_databases_loaded_restores_filters(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that database load restores pending filter state.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window._pending_filter_state = {
            "resolution": SupportedResolution.R_1080,
            "code": "SavedCode",
            "faction": None,
            "category": None,
            "mod": None,
            "crated_all": True,
            "crated_normal": False,
            "crated_crated": False,
        }

        mock_db = MagicMock()
        mock_db.templates = []
        all_databases = {SupportedResolution.R_1080: mock_db}

        with patch.object(visualizer_window, "_restore_filter_state") as mock_restore:
            visualizer_window._on_databases_loaded(all_databases)  # type: ignore[arg-type]
            mock_restore.assert_called_once()

        assert visualizer_window._pending_filter_state is None


class TestDatabaseVisualizerWindowCloseEvent:
    """Tests for window close event."""

    def test_close_event_waits_for_thread(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test close event waits for loader thread.

        Args:
            visualizer_window: Window fixture.
        """
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        visualizer_window.loader_thread = mock_thread

        mock_event = MagicMock()

        visualizer_window.closeEvent(mock_event)

        mock_thread.wait.assert_called_once()
        mock_event.accept.assert_called_once()

    def test_close_event_no_thread(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test close event with no loader thread.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.loader_thread = None

        mock_event = MagicMock()

        visualizer_window.closeEvent(mock_event)

        mock_event.accept.assert_called_once()


class TestDatabaseVisualizerWindowBrowseDatabase:
    """Tests for browse database functionality."""

    def test_browse_database_cancelled(self, visualizer_window: DatabaseVisualizerWindow) -> None:
        """Test browse database when user cancels dialog.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.database_path = "/original/path.h5"

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            visualizer_window._on_browse_database()

        # Path should remain unchanged
        assert visualizer_window.database_path == "/original/path.h5"

    def test_browse_database_selects_new_file(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test browse database when user selects a new file.

        Args:
            visualizer_window: Window fixture.
        """
        visualizer_window.database_path = "/original/path.h5"
        visualizer_window.all_databases = {SupportedResolution.R_1080: MagicMock()}
        visualizer_window.all_templates = [(0, MagicMock())]
        visualizer_window.filtered_templates = [(0, MagicMock())]

        with patch(
            "fs_tools.gui.windows.database_visualizer_window.QFileDialog.getOpenFileName",
            return_value=("/new/path.h5", ""),
        ):
            with patch.object(visualizer_window, "load_databases") as mock_load:
                visualizer_window._on_browse_database()

                # Path should be updated
                assert visualizer_window.database_path == "/new/path.h5"
                assert visualizer_window.database_path_edit.text() == "/new/path.h5"

                # State should be cleared
                assert visualizer_window.all_databases == {}
                assert visualizer_window.all_templates == []
                assert visualizer_window.filtered_templates == []
                assert visualizer_window.selected_template is None
                assert visualizer_window.database is None
                assert visualizer_window.current_resolution is None

                # load_databases should be called
                mock_load.assert_called_once()

    def test_database_path_edit_shows_initial_path(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that database path edit shows initial path.

        Args:
            visualizer_window: Window fixture.
        """
        # The fixture creates with database_path=None, so it should be empty
        assert visualizer_window.database_path_edit.text() == ""

    def test_database_path_edit_is_readonly(
        self, visualizer_window: DatabaseVisualizerWindow
    ) -> None:
        """Test that database path edit is read-only.

        Args:
            visualizer_window: Window fixture.
        """
        assert visualizer_window.database_path_edit.isReadOnly()
