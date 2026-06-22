"""Tests for the fs-tools launcher window."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fs_tools.gui.main_window import ToolsMainWindow
from fs_tools.gui.windows.catalog_builder_window import CatalogBuilderWindow
from fs_tools.gui.windows.icon_import_window import IconImportWindow


@pytest.fixture
def window(qtbot: Any) -> ToolsMainWindow:
    """Create a ToolsMainWindow instance.

    Args:
        qtbot: pytest-qt fixture.

    Returns:
        ToolsMainWindow: The window under test.
    """
    win = ToolsMainWindow()
    qtbot.addWidget(win)
    return win


def test_window_title(window: ToolsMainWindow) -> None:
    """The window title identifies the tools app."""
    assert "FS Tools" in window.windowTitle()


def test_show_icon_import(window: ToolsMainWindow) -> None:
    """Opening the icon import window instantiates and shows it."""
    with patch("fs_tools.gui.main_window.IconImportWindow") as mock_cls:
        window.show_icon_import()
        mock_cls.assert_called_once_with(window)
        mock_cls.return_value.show.assert_called_once()


def test_show_catalog_builder(window: ToolsMainWindow) -> None:
    """Opening the catalog builder window instantiates and shows it."""
    with patch("fs_tools.gui.main_window.CatalogBuilderWindow") as mock_cls:
        window.show_catalog_builder()
        mock_cls.assert_called_once_with(window)
        mock_cls.return_value.show.assert_called_once()


def test_show_database_visualizer_with_config(window: ToolsMainWindow) -> None:
    """The visualizer opens with the configured database path."""
    with patch.object(window, "_configured_database_path", return_value="/db.h5"):
        with patch("fs_tools.gui.main_window.DatabaseVisualizerWindow") as mock_cls:
            window.show_database_visualizer()
            mock_cls.assert_called_once_with(window, database_path="/db.h5")
            mock_cls.return_value.show.assert_called_once()


def test_show_database_visualizer_no_database(window: ToolsMainWindow) -> None:
    """Without a configured database the visualizer is not opened."""
    with patch.object(window, "_configured_database_path", return_value=None):
        with patch("fs_tools.gui.main_window.QMessageBox.warning") as mock_warn:
            with patch("fs_tools.gui.main_window.DatabaseVisualizerWindow") as mock_cls:
                window.show_database_visualizer()
                mock_cls.assert_not_called()
                mock_warn.assert_called_once()


def test_show_debug_viewer_with_config(window: ToolsMainWindow) -> None:
    """The debug viewer opens with the configured database path."""
    with patch.object(window, "_configured_database_path", return_value="/db.h5"):
        with patch("fs_tools.gui.main_window.DebugImageWindow") as mock_cls:
            window.show_debug_viewer()
            mock_cls.assert_called_once_with(window, database_path="/db.h5")
            mock_cls.return_value.show.assert_called_once()


def test_show_settings(window: ToolsMainWindow) -> None:
    """Opening the settings dialog instantiates and executes it."""
    with patch("fs_tools.gui.main_window.SettingsDialog") as mock_cls:
        window.show_settings()
        mock_cls.assert_called_once_with(window)
        mock_cls.return_value.exec.assert_called_once()


def test_tool_rows_enabled_when_configured(qtbot: Any) -> None:
    """All gated tool rows are enabled when their requirements are met."""
    settings = MagicMock()
    settings.scanner.database_path = "/db.h5"
    with (
        patch("fs_tools.gui.main_window.AppSettings", return_value=settings),
        patch.object(CatalogBuilderWindow, "requirements_met", return_value=True),
        patch.object(IconImportWindow, "requirements_met", return_value=True),
    ):
        win = ToolsMainWindow()
        qtbot.addWidget(win)
        assert win._catalog_builder_row.isEnabled()
        assert win._icon_import_row.isEnabled()
        assert win._visualizer_row.isEnabled()
        assert win._debug_viewer_row.isEnabled()


def test_tool_rows_disabled_when_unconfigured(qtbot: Any) -> None:
    """Gated tool rows are disabled when their requirements are missing."""
    settings = MagicMock()
    settings.scanner.database_path = None
    with (
        patch("fs_tools.gui.main_window.AppSettings", return_value=settings),
        patch.object(CatalogBuilderWindow, "requirements_met", return_value=False),
        patch.object(IconImportWindow, "requirements_met", return_value=False),
    ):
        win = ToolsMainWindow()
        qtbot.addWidget(win)
        assert not win._catalog_builder_row.isEnabled()
        assert not win._icon_import_row.isEnabled()
        assert not win._visualizer_row.isEnabled()
        assert not win._debug_viewer_row.isEnabled()
        # The database info tool has no prerequisite and stays enabled.
        assert win._database_info_row.isEnabled()


def test_show_database_info(window: ToolsMainWindow) -> None:
    """The database info dialog opens with the configured path."""
    with patch.object(window, "_configured_database_path", return_value="/db.h5"):
        with patch("fs_tools.gui.main_window.DatabaseInfoWindow") as mock_cls:
            window.show_database_info()
            mock_cls.assert_called_once_with(window, initial_db_path="/db.h5")
            mock_cls.return_value.show.assert_called_once()
