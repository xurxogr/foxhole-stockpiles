"""Tests for DebugImageWindow."""

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.stockpile import Stockpile
from fs_tools.gui.windows.debug_image_window import (
    DatabaseLoader,
    DebugImageWindow,
)
from fs_tools.models.debug_candidate import DebugCandidate
from fs_tools.models.detected_icon_info import DetectedIconInfo
from fs_tools.models.icon_template import IconTemplate
from fs_tools.models.scan_result import ScanResult
from fs_tools.template_db.template_database import TemplateDatabase


@pytest.fixture
def mock_stockpile() -> Stockpile:
    """Create a mock stockpile for testing.

    Returns:
        Stockpile: A mock stockpile instance.
    """
    return Stockpile(
        name="Test Stockpile",
        type=StockpileType.STORAGE_DEPOT,
        resolution="1920x1080",
        items=[],
    )


@pytest.fixture
def mock_detected_icon() -> DetectedIconInfo:
    """Create a mock detected icon for testing.

    Returns:
        DetectedIconInfo: A mock detected icon instance.
    """
    return DetectedIconInfo(
        index=0,
        code="TestItem",
        quantity=100,
        crated=False,
        confidence=0.95,
        icon_image=np.zeros((32, 32, 3), dtype=np.uint8),
        position=(100, 100),
        size=32,
    )


@pytest.fixture
def mock_crated_icon() -> DetectedIconInfo:
    """Create a mock crated detected icon for testing.

    Returns:
        DetectedIconInfo: A mock crated detected icon instance.
    """
    return DetectedIconInfo(
        index=1,
        code="TestItem",
        quantity=5,
        crated=True,
        confidence=0.92,
        icon_image=np.zeros((32, 32, 3), dtype=np.uint8),
        position=(150, 100),
        size=32,
    )


@pytest.fixture
def mock_scan_result(mock_stockpile: Stockpile, mock_detected_icon: DetectedIconInfo) -> ScanResult:
    """Create a mock scan result for testing.

    Args:
        mock_stockpile: Mock stockpile fixture.
        mock_detected_icon: Mock detected icon fixture.

    Returns:
        ScanResult: A mock scan result instance.
    """
    return ScanResult(
        stockpile=mock_stockpile,
        detected_icons=[mock_detected_icon],
        original_image=np.zeros((1080, 1920, 3), dtype=np.uint8),
    )


@pytest.fixture
def mock_template() -> IconTemplate:
    """Create a mock icon template for testing.

    Returns:
        IconTemplate: A mock template instance.
    """
    return IconTemplate(
        code="TestItem",
        crated=False,
        category=ItemCategory.Item,
        faction=ItemFaction.NEUTRAL,
        mod="vanilla",
        resolution=SupportedResolution.R_1080,
        image=np.zeros((32, 32, 3), dtype=np.uint8),
    )


@pytest.fixture
def mock_database() -> MagicMock:
    """Create a mock template database.

    Returns:
        MagicMock: A mock database instance.
    """
    db = MagicMock(spec=TemplateDatabase)
    db.templates = []
    return db


@pytest.fixture
def mock_database_with_templates(mock_template: IconTemplate) -> MagicMock:
    """Create a mock template database with templates.

    Args:
        mock_template: Mock template fixture.

    Returns:
        MagicMock: A mock database instance with templates.
    """
    db = MagicMock(spec=TemplateDatabase)
    db.templates = [mock_template]
    return db


@pytest.fixture
def debug_window(qtbot: Any) -> DebugImageWindow:
    """Create a DebugImageWindow instance without loading.

    Args:
        qtbot: PyQt test fixture.

    Returns:
        DebugImageWindow: Window instance.
    """
    window = DebugImageWindow(parent=None, database_path=None)
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

        with patch("fs_tools.gui.windows.debug_image_window.TemplateManager"):
            with patch(
                "fs_tools.gui.windows.debug_image_window.asyncio.run",
                return_value=mock_databases,
            ):
                # Connect signal to capture result
                result: list[Any] = []
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
            "fs_tools.gui.windows.debug_image_window.TemplateManager",
            side_effect=FileNotFoundError("Database not found"),
        ):
            # Connect signal to capture error
            errors: list[str] = []
            loader.error.connect(lambda x: errors.append(x))

            loader.run()

            assert len(errors) == 1
            assert "Database not found" in errors[0]


class TestDebugImageWindowInitialization:
    """Tests for DebugImageWindow initialization."""

    def test_initialization_without_path(self, qtbot: Any) -> None:
        """Test window initialization without database path.

        Args:
            qtbot: PyQt test fixture.
        """
        window = DebugImageWindow(parent=None, database_path=None)
        qtbot.addWidget(window)

        assert window.database_path is None
        assert window.all_databases == {}
        assert window.scan_result is None
        assert window.selected_icon is None
        assert window.loader_thread is None
        assert window.scan_worker is None

    def test_initialization_with_path(self, qtbot: Any) -> None:
        """Test window initialization with database path starts loading.

        Args:
            qtbot: PyQt test fixture.
        """
        with patch.object(DebugImageWindow, "load_databases") as mock_load:
            window = DebugImageWindow(parent=None, database_path="/path/to/db.h5")
            qtbot.addWidget(window)

            assert window.database_path == "/path/to/db.h5"
            mock_load.assert_called_once()

    def test_window_title(self, debug_window: DebugImageWindow) -> None:
        """Test initial window title.

        Args:
            debug_window: Window fixture.
        """
        assert t("debug_viewer.title") in debug_window.windowTitle()

    def test_minimum_size(self, debug_window: DebugImageWindow) -> None:
        """Test window minimum size.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.minimumWidth() >= 1400
        assert debug_window.minimumHeight() >= 800


class TestDebugImageWindowUI:
    """Tests for DebugImageWindow UI components."""

    def test_browse_button_exists(self, debug_window: DebugImageWindow) -> None:
        """Test that browse button is created.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.browse_button is not None
        assert debug_window.browse_button.text() == t("common.browse")

    def test_path_edit_exists(self, debug_window: DebugImageWindow) -> None:
        """Test that path edit is created and read-only.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.path_edit is not None
        assert debug_window.path_edit.isReadOnly()

    def test_items_list_exists(self, debug_window: DebugImageWindow) -> None:
        """Test that items list is created.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.items_list is not None
        assert debug_window.items_list.count() == 0

    def test_screenshot_label_exists(self, debug_window: DebugImageWindow) -> None:
        """Test that screenshot label is created.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.screenshot_label is not None

    def test_comparison_layout_exists(self, debug_window: DebugImageWindow) -> None:
        """Test that comparison layout is created.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.comparison_layout is not None
        assert debug_window.comparison_widget is not None

    def test_groups_have_correct_titles(self, debug_window: DebugImageWindow) -> None:
        """Test that group boxes have correct titles.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.items_group.title() == t("debug_viewer.detected_items")
        assert debug_window.screenshot_group.title() == t("debug_viewer.screenshot")
        assert debug_window.comparison_group.title() == t("debug_viewer.icon_comparison")


class TestDebugImageWindowBrowse:
    """Tests for browse screenshot functionality."""

    def test_browse_cancelled(self, debug_window: DebugImageWindow) -> None:
        """Test browse when user cancels dialog.

        Args:
            debug_window: Window fixture.
        """
        with patch(
            "fs_tools.gui.windows.debug_image_window.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            with patch.object(debug_window, "_scan_screenshot") as mock_scan:
                debug_window._on_browse_screenshot()
                mock_scan.assert_not_called()

    def test_browse_selects_file(self, debug_window: DebugImageWindow) -> None:
        """Test browse when user selects a file.

        Args:
            debug_window: Window fixture.
        """
        with patch(
            "fs_tools.gui.windows.debug_image_window.QFileDialog.getOpenFileName",
            return_value=("/path/to/screenshot.png", ""),
        ):
            with patch.object(debug_window, "_scan_screenshot") as mock_scan:
                debug_window._on_browse_screenshot()

                assert debug_window.path_edit.text() == "/path/to/screenshot.png"
                mock_scan.assert_called_once_with("/path/to/screenshot.png")


class TestDebugImageWindowScan:
    """Tests for screenshot scanning functionality."""

    def test_scan_without_database_path(self, debug_window: DebugImageWindow) -> None:
        """Test scanning without database path shows warning.

        Args:
            debug_window: Window fixture.
        """
        debug_window.database_path = None

        with patch("fs_tools.gui.windows.debug_image_window.QMessageBox.warning") as mock_warning:
            debug_window._scan_screenshot("/path/to/screenshot.png")
            mock_warning.assert_called_once()

    def test_scan_clears_previous_results(self, debug_window: DebugImageWindow) -> None:
        """Test that scanning clears previous results.

        Args:
            debug_window: Window fixture.
        """
        debug_window.database_path = "/path/to/db.h5"
        debug_window.scan_result = MagicMock()
        debug_window.selected_icon = MagicMock()

        # Add a dummy item to the list
        debug_window.items_list.addItem("Test Item")

        with patch("fs_tools.gui.windows.debug_image_window.ImageScanWorker") as mock_worker_class:
            mock_worker = MagicMock()
            mock_worker_class.return_value = mock_worker

            debug_window._scan_screenshot("/path/to/screenshot.png")

            assert debug_window.items_list.count() == 0
            assert debug_window.scan_result is None
            assert debug_window.selected_icon is None

    def test_scan_starts_worker(self, debug_window: DebugImageWindow) -> None:
        """Test that scanning starts the worker thread.

        Args:
            debug_window: Window fixture.
        """
        debug_window.database_path = "/path/to/db.h5"

        with patch("fs_tools.gui.windows.debug_image_window.ImageScanWorker") as mock_worker_class:
            mock_worker = MagicMock()
            mock_worker_class.return_value = mock_worker

            debug_window._scan_screenshot("/path/to/screenshot.png")

            mock_worker.start.assert_called_once()
            assert debug_window.scan_worker is mock_worker


class TestDebugImageWindowScanResults:
    """Tests for scan result handling."""

    def test_on_scan_finished_populates_list(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test successful scan populates items list.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
        """
        with patch.object(debug_window, "_display_screenshot"):
            debug_window._on_scan_finished(mock_scan_result)

            assert debug_window.scan_result == mock_scan_result
            assert debug_window.items_list.count() == 1

    def test_on_scan_finished_item_format(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test scan result item format in list.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
        """
        with patch.object(debug_window, "_display_screenshot"):
            debug_window._on_scan_finished(mock_scan_result)

            item = debug_window.items_list.item(0)
            assert item is not None
            text = item.text()
            # Format: "000: TestItem x100 (95.0%)"
            assert "000:" in text
            assert "TestItem" in text
            assert "x100" in text
            assert "95.0%" in text

    def test_on_scan_finished_crated_item_format(
        self,
        debug_window: DebugImageWindow,
        mock_stockpile: Stockpile,
        mock_crated_icon: DetectedIconInfo,
    ) -> None:
        """Test scan result crated item format in list.

        Args:
            debug_window: Window fixture.
            mock_stockpile: Mock stockpile.
            mock_crated_icon: Mock crated icon.
        """
        scan_result = ScanResult(
            stockpile=mock_stockpile,
            detected_icons=[mock_crated_icon],
            original_image=np.zeros((1080, 1920, 3), dtype=np.uint8),
        )

        with patch.object(debug_window, "_display_screenshot"):
            debug_window._on_scan_finished(scan_result)

            item = debug_window.items_list.item(0)
            assert item is not None
            text = item.text()
            assert "[Crated]" in text

    def test_on_scan_finished_auto_selects_first(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test scan auto-selects first item.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
        """
        with patch.object(debug_window, "_display_screenshot"):
            debug_window._on_scan_finished(mock_scan_result)

            assert debug_window.items_list.currentRow() == 0

    def test_on_scan_finished_displays_screenshot(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test scan displays screenshot.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
        """
        with patch.object(debug_window, "_display_screenshot") as mock_display:
            debug_window._on_scan_finished(mock_scan_result)

            # Called at least once (may be called again during auto-select)
            mock_display.assert_called()

    def test_on_scan_error_shows_warning(self, debug_window: DebugImageWindow) -> None:
        """Test scan error shows warning dialog.

        Args:
            debug_window: Window fixture.
        """
        with patch("fs_tools.gui.windows.debug_image_window.QMessageBox.warning") as mock_warning:
            debug_window._on_scan_error("Test error message")

            mock_warning.assert_called_once()
            call_args = mock_warning.call_args[0]
            assert "Test error message" in call_args[2]


class TestDebugImageWindowItemSelection:
    """Tests for item selection handling."""

    def test_on_item_changed_none(self, debug_window: DebugImageWindow) -> None:
        """Test item change with None current.

        Args:
            debug_window: Window fixture.
        """
        with patch.object(debug_window, "_display_screenshot") as mock_display:
            with patch.object(debug_window, "_update_comparison") as mock_update:
                debug_window._on_item_changed(None, None)

                mock_display.assert_not_called()
                mock_update.assert_not_called()

    def test_on_item_changed_updates_selected(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test item change updates selected icon.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
        """
        debug_window.scan_result = mock_scan_result

        item = QListWidgetItem("Test Item")
        item.setData(Qt.ItemDataRole.UserRole, mock_detected_icon)

        with patch.object(debug_window, "_display_screenshot"):
            with patch.object(debug_window, "_update_comparison"):
                debug_window._on_item_changed(item, None)

                assert debug_window.selected_icon == mock_detected_icon

    def test_on_item_changed_highlights_screenshot(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test item change highlights icon in screenshot.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
        """
        debug_window.scan_result = mock_scan_result

        item = QListWidgetItem("Test Item")
        item.setData(Qt.ItemDataRole.UserRole, mock_detected_icon)

        with patch.object(debug_window, "_display_screenshot") as mock_display:
            with patch.object(debug_window, "_update_comparison"):
                debug_window._on_item_changed(item, None)

                mock_display.assert_called_once_with(
                    mock_scan_result.original_image, mock_detected_icon
                )

    def test_on_item_changed_updates_comparison(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test item change updates comparison panel.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
        """
        debug_window.scan_result = mock_scan_result

        item = QListWidgetItem("Test Item")
        item.setData(Qt.ItemDataRole.UserRole, mock_detected_icon)

        with patch.object(debug_window, "_display_screenshot"):
            with patch.object(debug_window, "_update_comparison") as mock_update:
                debug_window._on_item_changed(item, None)

                mock_update.assert_called_once_with(mock_detected_icon)


class TestDebugImageWindowComparison:
    """Tests for comparison panel functionality."""

    def test_update_comparison_no_databases(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
    ) -> None:
        """Test update comparison with no databases.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
        """
        debug_window.all_databases = {}

        with patch.object(debug_window, "_clear_comparison") as mock_clear:
            debug_window._update_comparison(mock_detected_icon)

            mock_clear.assert_called_once()

    def test_update_comparison_no_scan_result(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_database: MagicMock,
    ) -> None:
        """Test update comparison with no scan result.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_database: Mock database.
        """
        debug_window.all_databases = {SupportedResolution.R_1080: mock_database}
        debug_window.scan_result = None

        with patch.object(debug_window, "_clear_comparison") as mock_clear:
            debug_window._update_comparison(mock_detected_icon)

            mock_clear.assert_called_once()

    def test_clear_comparison(self, debug_window: DebugImageWindow) -> None:
        """Test clearing comparison panel.

        Args:
            debug_window: Window fixture.
        """
        # Add some widgets
        from PySide6.QtWidgets import QLabel

        debug_window.comparison_layout.addWidget(QLabel("Test"))
        debug_window.comparison_layout.addWidget(QLabel("Test2"))

        assert debug_window.comparison_layout.count() == 2

        debug_window._clear_comparison()

        assert debug_window.comparison_layout.count() == 0

    def test_update_comparison_with_databases_and_templates(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
        mock_template: IconTemplate,
    ) -> None:
        """Test update comparison with matching templates.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
            mock_template: Mock template.
        """
        # Create database with matching template
        db = MagicMock(spec=TemplateDatabase)
        db.templates = [mock_template]

        debug_window.all_databases = {SupportedResolution.R_1080: db}
        debug_window.scan_result = mock_scan_result

        # Should add widgets to comparison layout
        debug_window._update_comparison(mock_detected_icon)

        # Should have added widgets: detected icon + separator + template + stretch
        assert debug_window.comparison_layout.count() > 0

    def test_update_comparison_filters_candidates_by_phash(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
        mock_template: IconTemplate,
    ) -> None:
        """fs-ocr candidates beyond the pHash threshold are filtered; the rest render.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result (resolution 1920x1080).
            mock_template: Template the candidate maps back to (code 'TestItem',
                mod 'vanilla', neutral, uncrated).
        """
        db = MagicMock(spec=TemplateDatabase)
        db.templates = [mock_template]
        debug_window.all_databases = {SupportedResolution.R_1080: db}
        debug_window.scan_result = mock_scan_result

        near = DebugCandidate(
            code="TestItem",
            mod="vanilla",
            category="item",
            crated=False,
            faction="neutral",
            confidence=0.97,
            phash_distance=3,
        )
        far = DebugCandidate(
            code="TestItem",
            mod="vanilla",
            category="item",
            crated=False,
            faction="neutral",
            confidence=0.40,
            phash_distance=40,
        )
        icon = DetectedIconInfo(
            index=0,
            code="TestItem",
            quantity=1,
            crated=False,
            confidence=0.99,
            icon_image=np.zeros((32, 32, 3), dtype=np.uint8),
            position=(0, 0),
            size=32,
            candidates=[near, far],
        )

        debug_window._update_comparison(icon)

        # Default pHash threshold is 15, so the distance-40 candidate is dropped;
        # widgets = detected icon + settings + separator + 1 candidate + stretch.
        assert debug_window.comparison_layout.count() == 5

    def test_update_comparison_with_multiple_resolutions(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test update comparison with multiple resolution databases.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
        """
        # Create templates for different resolutions
        template_1080 = IconTemplate(
            code="TestItem",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
        )
        template_1440 = IconTemplate(
            code="TestItem",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1440,
            image=np.zeros((48, 48, 3), dtype=np.uint8),
        )

        db_1080 = MagicMock(spec=TemplateDatabase)
        db_1080.templates = [template_1080]

        db_1440 = MagicMock(spec=TemplateDatabase)
        db_1440.templates = [template_1440]

        debug_window.all_databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
        }
        debug_window.scan_result = mock_scan_result

        debug_window._update_comparison(mock_detected_icon)

        # Should have added widgets for both resolutions
        assert debug_window.comparison_layout.count() > 0

    def test_update_comparison_no_matching_template(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test update comparison when no template matches.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
        """
        # Create template with different code
        template = IconTemplate(
            code="DifferentItem",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
        )

        db = MagicMock(spec=TemplateDatabase)
        db.templates = [template]

        debug_window.all_databases = {SupportedResolution.R_1080: db}
        debug_window.scan_result = mock_scan_result

        debug_window._update_comparison(mock_detected_icon)

        # Should still add detected icon widget even if no template matches
        assert debug_window.comparison_layout.count() > 0

    def test_update_comparison_empty_templates(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test update comparison with empty template list.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
            mock_scan_result: Mock scan result.
        """
        db = MagicMock(spec=TemplateDatabase)
        db.templates = []  # Empty templates

        debug_window.all_databases = {SupportedResolution.R_1080: db}
        debug_window.scan_result = mock_scan_result

        # Should not raise, just use default target size
        debug_window._update_comparison(mock_detected_icon)

        assert debug_window.comparison_layout.count() > 0


class TestDebugImageWindowDisplayScreenshot:
    """Tests for screenshot display functionality."""

    def test_display_screenshot_without_highlight(self, debug_window: DebugImageWindow) -> None:
        """Test displaying screenshot without highlight.

        Args:
            debug_window: Window fixture.
        """
        image = np.zeros((100, 100, 3), dtype=np.uint8)

        # Should not raise
        debug_window._display_screenshot(image)

        assert not debug_window.screenshot_label.pixmap().isNull()

    def test_display_screenshot_with_highlight(
        self,
        debug_window: DebugImageWindow,
        mock_detected_icon: DetectedIconInfo,
    ) -> None:
        """Test displaying screenshot with highlight.

        Args:
            debug_window: Window fixture.
            mock_detected_icon: Mock detected icon.
        """
        image = np.zeros((200, 200, 3), dtype=np.uint8)

        # Should not raise
        debug_window._display_screenshot(image, mock_detected_icon)

        assert not debug_window.screenshot_label.pixmap().isNull()


class TestDebugImageWindowGetScreenshotResolution:
    """Tests for screenshot resolution detection."""

    def test_get_screenshot_resolution_no_scan_result(self, debug_window: DebugImageWindow) -> None:
        """Test resolution detection with no scan result.

        Args:
            debug_window: Window fixture.
        """
        debug_window.scan_result = None

        result = debug_window._get_screenshot_resolution()

        assert result is None

    def test_get_screenshot_resolution_no_resolution_field(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test resolution detection with no resolution field.

        Args:
            debug_window: Window fixture.
        """
        mock_stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            resolution=None,
            items=[],
        )
        debug_window.scan_result = ScanResult(
            stockpile=mock_stockpile,
            detected_icons=[],
            original_image=np.zeros((100, 100, 3), dtype=np.uint8),
        )

        result = debug_window._get_screenshot_resolution()

        assert result is None

    def test_get_screenshot_resolution_1080p(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test resolution detection for 1080p.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result with 1920x1080 resolution.
        """
        debug_window.scan_result = mock_scan_result

        result = debug_window._get_screenshot_resolution()

        assert result == SupportedResolution.R_1080

    def test_get_screenshot_resolution_invalid_format(self, debug_window: DebugImageWindow) -> None:
        """Test resolution detection with invalid format.

        Args:
            debug_window: Window fixture.
        """
        mock_stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            resolution="invalid",
            items=[],
        )
        debug_window.scan_result = ScanResult(
            stockpile=mock_stockpile,
            detected_icons=[],
            original_image=np.zeros((100, 100, 3), dtype=np.uint8),
        )

        result = debug_window._get_screenshot_resolution()

        assert result is None


class TestDebugImageWindowDatabaseLoading:
    """Tests for database loading functionality."""

    def test_load_databases_no_path(self, debug_window: DebugImageWindow) -> None:
        """Test load_databases with no path returns early.

        Args:
            debug_window: Window fixture.
        """
        debug_window.database_path = None

        with patch.object(DatabaseLoader, "start") as mock_start:
            debug_window.load_databases()

            mock_start.assert_not_called()

    def test_load_databases_starts_thread(self, debug_window: DebugImageWindow) -> None:
        """Test load_databases starts loader thread.

        Args:
            debug_window: Window fixture.
        """
        debug_window.database_path = "/path/to/db.h5"

        with patch.object(DatabaseLoader, "start") as mock_start:
            debug_window.load_databases()

            assert debug_window.loader_thread is not None
            mock_start.assert_called_once()

    def test_on_databases_loaded(
        self,
        debug_window: DebugImageWindow,
        mock_database: MagicMock,
    ) -> None:
        """Test successful database load handling.

        Args:
            debug_window: Window fixture.
            mock_database: Mock database.
        """
        all_databases: dict[SupportedResolution, TemplateDatabase] = {
            SupportedResolution.R_1080: mock_database,
        }

        debug_window._on_databases_loaded(all_databases)

        assert debug_window.all_databases == all_databases

    def test_on_database_error(self, debug_window: DebugImageWindow) -> None:
        """Test database error handling.

        Args:
            debug_window: Window fixture.
        """
        with patch("fs_tools.gui.windows.debug_image_window.QMessageBox.warning") as mock_warning:
            debug_window._on_database_error("Test error message")

            mock_warning.assert_called_once()


class TestDebugImageWindowLanguageChange:
    """Tests for language change handling."""

    def test_on_language_changed(self, debug_window: DebugImageWindow) -> None:
        """Test language change triggers retranslate.

        Args:
            debug_window: Window fixture.
        """
        with patch.object(debug_window, "retranslate") as mock_retranslate:
            debug_window._on_language_changed("es")
            mock_retranslate.assert_called_once()

    def test_retranslate_updates_ui(self, debug_window: DebugImageWindow) -> None:
        """Test retranslate updates UI elements.

        Args:
            debug_window: Window fixture.
        """
        debug_window.retranslate()

        assert debug_window.windowTitle() == t("debug_viewer.title")
        assert debug_window.browse_button.text() == t("common.browse")


class TestDebugImageWindowCloseEvent:
    """Tests for window close event."""

    def test_close_event_waits_for_loader_thread(self, debug_window: DebugImageWindow) -> None:
        """Test close event waits for loader thread.

        Args:
            debug_window: Window fixture.
        """
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        debug_window.loader_thread = mock_thread

        mock_event = MagicMock()
        mock_event.accept = MagicMock()

        debug_window.closeEvent(mock_event)

        mock_thread.wait.assert_called_once()
        mock_event.accept.assert_called_once()

    def test_close_event_waits_for_scan_worker(self, debug_window: DebugImageWindow) -> None:
        """Test close event waits for scan worker.

        Args:
            debug_window: Window fixture.
        """
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        debug_window.scan_worker = mock_worker

        mock_event = MagicMock()
        mock_event.accept = MagicMock()

        debug_window.closeEvent(mock_event)

        mock_worker.wait.assert_called_once()
        mock_event.accept.assert_called_once()

    def test_close_event_no_threads(self, debug_window: DebugImageWindow) -> None:
        """Test close event with no threads.

        Args:
            debug_window: Window fixture.
        """
        debug_window.loader_thread = None
        debug_window.scan_worker = None

        mock_event = MagicMock()
        mock_event.accept = MagicMock()

        debug_window.closeEvent(mock_event)

        mock_event.accept.assert_called_once()


class TestDebugImageWindowAddSeparator:
    """Tests for separator functionality."""

    def test_add_separator(self, debug_window: DebugImageWindow) -> None:
        """Test adding separator to comparison layout.

        Args:
            debug_window: Window fixture.
        """
        initial_count = debug_window.comparison_layout.count()

        debug_window._add_separator()

        assert debug_window.comparison_layout.count() == initial_count + 1


class TestDebugImageWindowSummary:
    """Tests for summary label functionality."""

    def test_summary_label_exists(self, debug_window: DebugImageWindow) -> None:
        """Test that summary label is created.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.summary_label is not None

    def test_summary_label_single_line(self, debug_window: DebugImageWindow) -> None:
        """Test that summary label is configured for single line.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.summary_label.wordWrap() is False

    def test_update_summary_with_full_data(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test summary update with all fields populated.

        Args:
            debug_window: Window fixture.
        """
        stockpile = Stockpile(
            name="Test Stockpile",
            type=StockpileType.SEAPORT,
            resolution="1920x1080",
            shard="ABLE",
            ingame_timestamp="Day 100, 1200 Hours",
            items=[],
        )
        scan_result = ScanResult(
            stockpile=stockpile,
            detected_icons=[],
            original_image=np.zeros((1080, 1920, 3), dtype=np.uint8),
        )

        debug_window._update_summary(scan_result)

        text = debug_window.summary_label.text()
        # Labels are now bold with HTML tags
        assert f"<b>{t('debug_viewer.summary_type')}:</b>" in text
        assert f"<b>{t('debug_viewer.summary_name')}:</b>" in text
        assert "Test Stockpile" in text
        assert f"<b>{t('debug_viewer.summary_shard')}:</b>" in text
        assert "ABLE" in text
        assert f"<b>{t('debug_viewer.summary_time')}:</b>" in text
        assert "Day 100" in text

    def test_update_summary_without_name(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test summary update without stockpile name.

        Args:
            debug_window: Window fixture.
        """
        stockpile = Stockpile(
            name="",
            type=StockpileType.STORAGE_DEPOT,
            resolution="1920x1080",
            shard="BAKER",
            items=[],
        )
        scan_result = ScanResult(
            stockpile=stockpile,
            detected_icons=[],
            original_image=np.zeros((1080, 1920, 3), dtype=np.uint8),
        )

        debug_window._update_summary(scan_result)

        text = debug_window.summary_label.text()
        assert f"<b>{t('debug_viewer.summary_type')}:</b>" in text
        assert f"<b>{t('debug_viewer.summary_name')}:</b>" not in text

    def test_on_scan_finished_updates_summary(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
    ) -> None:
        """Test that scan finished updates summary label.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
        """
        with patch.object(debug_window, "_display_screenshot"):
            debug_window._on_scan_finished(mock_scan_result)

            # Summary should have been updated with stockpile type (bold)
            text = debug_window.summary_label.text()
            assert f"<b>{t('debug_viewer.summary_type')}:</b>" in text


class TestDebugImageWindowSettings:
    """Tests for settings spinbox functionality."""

    def test_settings_spinboxes_initialized_none(self, debug_window: DebugImageWindow) -> None:
        """Test that settings spinboxes are initially None.

        Args:
            debug_window: Window fixture.
        """
        assert debug_window.phash_spinbox is None
        assert debug_window.ncc_spinbox is None

    def test_create_settings_widget_creates_spinboxes(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test that create_settings_widget creates spinboxes.

        Args:
            debug_window: Window fixture.
        """
        widget = debug_window._create_settings_widget()
        # Keep widget reference to prevent Qt from deleting it
        debug_window.comparison_layout.addWidget(widget)

        assert widget is not None
        assert debug_window.phash_spinbox is not None
        assert debug_window.ncc_spinbox is not None

    def test_create_settings_widget_default_values(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test that settings widget uses app settings defaults.

        Args:
            debug_window: Window fixture.
        """
        from fs_tools.gui.windows.debug_image_window import (
            DEFAULT_MAX_NCC_CANDIDATES,
            DEFAULT_PHASH_THRESHOLD,
        )

        widget = debug_window._create_settings_widget()
        # Keep widget reference to prevent Qt from deleting it
        debug_window.comparison_layout.addWidget(widget)

        assert debug_window.phash_spinbox is not None
        assert debug_window.ncc_spinbox is not None
        assert debug_window.phash_spinbox.value() == DEFAULT_PHASH_THRESHOLD
        assert debug_window.ncc_spinbox.value() == DEFAULT_MAX_NCC_CANDIDATES

    def test_create_settings_widget_custom_values(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test that settings widget accepts custom values.

        Args:
            debug_window: Window fixture.
        """
        widget = debug_window._create_settings_widget(phash_value=20, ncc_value=50)
        # Keep widget reference to prevent Qt from deleting it
        debug_window.comparison_layout.addWidget(widget)

        assert debug_window.phash_spinbox is not None
        assert debug_window.ncc_spinbox is not None
        assert debug_window.phash_spinbox.value() == 20
        assert debug_window.ncc_spinbox.value() == 50

    def test_on_settings_changed_triggers_update(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
        mock_detected_icon: DetectedIconInfo,
    ) -> None:
        """Test that settings change triggers comparison update.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
            mock_detected_icon: Mock detected icon.
        """
        debug_window.scan_result = mock_scan_result
        debug_window.selected_icon = mock_detected_icon

        with patch.object(debug_window, "_update_comparison") as mock_update:
            debug_window._on_settings_changed()

            mock_update.assert_called_once_with(mock_detected_icon)

    def test_on_settings_changed_no_selected_icon(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test that settings change does nothing without selected icon.

        Args:
            debug_window: Window fixture.
        """
        debug_window.selected_icon = None

        with patch.object(debug_window, "_update_comparison") as mock_update:
            debug_window._on_settings_changed()

            mock_update.assert_not_called()


class TestDebugImageWindowResize:
    """Tests for resize event handling."""

    def test_resize_event_updates_screenshot(
        self,
        debug_window: DebugImageWindow,
        mock_scan_result: ScanResult,
        mock_detected_icon: DetectedIconInfo,
    ) -> None:
        """Test that resize event re-displays screenshot.

        Args:
            debug_window: Window fixture.
            mock_scan_result: Mock scan result.
            mock_detected_icon: Mock detected icon.
        """
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent

        debug_window.scan_result = mock_scan_result
        debug_window.selected_icon = mock_detected_icon

        with patch.object(debug_window, "_display_screenshot") as mock_display:
            event = QResizeEvent(QSize(800, 600), QSize(640, 480))
            debug_window.resizeEvent(event)

            mock_display.assert_called_once_with(
                mock_scan_result.original_image, mock_detected_icon
            )

    def test_resize_event_no_scan_result(
        self,
        debug_window: DebugImageWindow,
    ) -> None:
        """Test that resize event does nothing without scan result.

        Args:
            debug_window: Window fixture.
        """
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent

        debug_window.scan_result = None

        with patch.object(debug_window, "_display_screenshot") as mock_display:
            event = QResizeEvent(QSize(800, 600), QSize(640, 480))
            debug_window.resizeEvent(event)

            mock_display.assert_not_called()


class TestDebugImageWindowCreateIconDisplay:
    """Tests for icon display widget creation."""

    def test_create_icon_display_detected(self, debug_window: DebugImageWindow) -> None:
        """Test creating icon display for detected icon.

        Args:
            debug_window: Window fixture.
        """
        image = np.zeros((32, 32, 3), dtype=np.uint8)

        widget = debug_window._create_icon_display(
            image=image,
            label="Detected",
            sublabel="(scaled)",
            ncc_score=None,
            target_size=32,
        )

        assert widget is not None

    def test_create_icon_display_with_ncc_high(self, debug_window: DebugImageWindow) -> None:
        """Test creating icon display with high NCC score (green).

        Args:
            debug_window: Window fixture.
        """
        image = np.zeros((32, 32, 3), dtype=np.uint8)

        widget = debug_window._create_icon_display(
            image=image,
            label="vanilla",
            sublabel="(1080p)",
            ncc_score=0.97,
            target_size=32,
        )

        assert widget is not None

    def test_create_icon_display_with_ncc_medium(self, debug_window: DebugImageWindow) -> None:
        """Test creating icon display with medium NCC score (orange).

        Args:
            debug_window: Window fixture.
        """
        image = np.zeros((32, 32, 3), dtype=np.uint8)

        widget = debug_window._create_icon_display(
            image=image,
            label="vanilla",
            sublabel="(1080p)",
            ncc_score=0.92,
            target_size=32,
        )

        assert widget is not None

    def test_create_icon_display_with_ncc_low(self, debug_window: DebugImageWindow) -> None:
        """Test creating icon display with low NCC score (red).

        Args:
            debug_window: Window fixture.
        """
        image = np.zeros((32, 32, 3), dtype=np.uint8)

        widget = debug_window._create_icon_display(
            image=image,
            label="vanilla",
            sublabel="(1080p)",
            ncc_score=0.85,
            target_size=32,
        )

        assert widget is not None

    def test_create_icon_display_resizes_image(self, debug_window: DebugImageWindow) -> None:
        """Test creating icon display resizes non-matching image.

        Args:
            debug_window: Window fixture.
        """
        # Image with different size than target
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        widget = debug_window._create_icon_display(
            image=image,
            label="vanilla",
            sublabel="(1080p)",
            ncc_score=0.95,
            target_size=32,
        )

        assert widget is not None

    def test_create_icon_display_no_sublabel(self, debug_window: DebugImageWindow) -> None:
        """Test creating icon display without sublabel.

        Args:
            debug_window: Window fixture.
        """
        image = np.zeros((32, 32, 3), dtype=np.uint8)

        widget = debug_window._create_icon_display(
            image=image,
            label="vanilla",
            sublabel=None,
            ncc_score=0.95,
            target_size=32,
        )

        assert widget is not None
