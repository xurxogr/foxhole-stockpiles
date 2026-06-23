"""Tests for MainWindow."""

from typing import Any
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMenuBar

from foxhole_stockpiles.gui.windows.main_window import MainWindow
from foxhole_stockpiles.i18n import t


@pytest.fixture
def window(qtbot: Any) -> MainWindow:
    """Create a MainWindow instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        MainWindow: Window instance
    """
    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_window_initialization(window: MainWindow) -> None:
    """Test MainWindow initialization.

    Args:
        window (MainWindow): Window instance
    """
    assert "FS (Foxhole Stockpiles)" in window.windowTitle()
    assert window.capture_panel is not None
    assert window.centralWidget() == window.capture_panel


def test_window_has_menu_bar(window: MainWindow) -> None:
    """Test MainWindow has menu bar.

    Args:
        window (MainWindow): Window instance
    """
    menu_bar = window.menuBar()
    assert menu_bar is not None
    assert isinstance(menu_bar, QMenuBar)


def test_window_file_menu_exists(window: MainWindow) -> None:
    """Test File menu exists.

    Args:
        window (MainWindow): Window instance
    """
    menu_bar = window.menuBar()
    assert menu_bar is not None
    actions = menu_bar.actions()

    file_menu_found = False
    for action in actions:
        if action.text() == t("main_window.menu.file"):
            file_menu_found = True
            break

    assert file_menu_found


def test_window_help_menu_exists(window: MainWindow) -> None:
    """Test Help menu exists.

    Args:
        window (MainWindow): Window instance
    """
    menu_bar = window.menuBar()
    assert menu_bar is not None
    actions = menu_bar.actions()

    help_menu_found = False
    for action in actions:
        if action.text() == t("main_window.menu.help"):
            help_menu_found = True
            break

    assert help_menu_found


def test_window_show_configuration(qtbot: Any, window: MainWindow) -> None:
    """Test showing configuration window.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    with patch("foxhole_stockpiles.gui.windows.main_window.ConfigWindow") as mock_config_class:
        mock_config = mock_config_class.return_value

        window.show_configuration()

        mock_config_class.assert_called_once_with(window)
        mock_config.setWindowModality.assert_called_once()
        mock_config.show.assert_called_once()


def test_window_show_about(qtbot: Any, window: MainWindow) -> None:
    """Test showing about dialog.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    with patch("foxhole_stockpiles.gui.windows.main_window.QMessageBox.about") as mock_about:
        window.show_about()

        mock_about.assert_called_once()
        call_args = mock_about.call_args
        assert call_args[0][0] == window
        assert call_args[0][1] == t("about.title")
        assert t("about.app_name") in call_args[0][2]


def test_window_scan_screenshot(qtbot: Any, window: MainWindow) -> None:
    """Test scanning screenshot from menu.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    with patch.object(window.capture_panel, "scan_screenshot_from_menu") as mock_scan:
        window.scan_screenshot()

        mock_scan.assert_called_once()


def test_window_quit_application(qtbot: Any, window: MainWindow) -> None:
    """Test quitting application.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    from PySide6.QtWidgets import QApplication

    with patch.object(QApplication, "quit") as mock_quit:
        window.quit_application()

        mock_quit.assert_called_once()


def test_tray_icon_creation_when_available(qtbot: Any) -> None:
    """Test tray icon is created when system tray is available.

    Args:
        qtbot: PyQt test fixture
    """
    from PySide6.QtWidgets import QSystemTrayIcon

    from foxhole_stockpiles.core.settings.sections.gui import GUISettings

    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True):
            with patch("foxhole_stockpiles.gui.windows.main_window.AppSettings") as mock_settings:
                # Default config has minimize_to_tray=False
                mock_settings.return_value.gui = GUISettings(minimize_to_tray=False)

                window = MainWindow()
                qtbot.addWidget(window)

                assert hasattr(window, "tray_icon")
                assert window.tray_icon is not None
                assert window.minimize_to_tray is False  # Default value


def test_tray_icon_creation_when_not_available(qtbot: Any) -> None:
    """Test tray icon is not created when system tray is not available.

    Args:
        qtbot: PyQt test fixture
    """
    from PySide6.QtWidgets import QSystemTrayIcon

    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            window = MainWindow()
            qtbot.addWidget(window)

            assert window.minimize_to_tray is False


def test_tray_icon_activated_double_click(qtbot: Any, window: MainWindow) -> None:
    """Test tray icon double-click shows window.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    from PySide6.QtWidgets import QSystemTrayIcon

    with patch.object(window, "show_from_tray") as mock_show:
        window.tray_icon_activated(QSystemTrayIcon.ActivationReason.DoubleClick)

        mock_show.assert_called_once()


def test_tray_icon_activated_single_click(qtbot: Any, window: MainWindow) -> None:
    """Test tray icon single-click does nothing.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    from PySide6.QtWidgets import QSystemTrayIcon

    with patch.object(window, "show_from_tray") as mock_show:
        window.tray_icon_activated(QSystemTrayIcon.ActivationReason.Trigger)

        mock_show.assert_not_called()


def test_show_from_tray(qtbot: Any, window: MainWindow) -> None:
    """Test showing window from tray.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    window.hide()
    assert not window.isVisible()

    window.show_from_tray()

    assert window.isVisible()


def test_load_minimize_to_tray_from_config(qtbot: Any) -> None:
    """Test loading minimize to tray setting from config.

    Args:
        qtbot: PyQt test fixture
    """
    from PySide6.QtWidgets import QSystemTrayIcon

    from foxhole_stockpiles.core.settings.sections.gui import GUISettings

    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True):
            with patch("foxhole_stockpiles.gui.windows.main_window.AppSettings") as mock_settings:
                mock_settings.return_value.gui = GUISettings(minimize_to_tray=True)

                window = MainWindow()
                qtbot.addWidget(window)

                assert window.minimize_to_tray is True


def test_load_minimize_to_tray_default_on_error(qtbot: Any) -> None:
    """Test minimize to tray defaults to False on config error.

    Args:
        qtbot: PyQt test fixture
    """
    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch(
            "foxhole_stockpiles.gui.windows.main_window.AppSettings",
            side_effect=OSError("Config error"),
        ):
            window = MainWindow()
            qtbot.addWidget(window)

            assert window.minimize_to_tray is False


def test_on_config_closed_reloads_settings(qtbot: Any, window: MainWindow) -> None:
    """Test that _on_config_closed reloads settings.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    from foxhole_stockpiles.core.settings.sections.gui import GUISettings

    with patch("foxhole_stockpiles.gui.windows.main_window.AppSettings") as mock_settings:
        mock_settings.return_value.gui = GUISettings(minimize_to_tray=True)

        window._on_config_closed()

        assert window.minimize_to_tray is True


def test_close_event_minimize_to_tray_enabled(qtbot: Any) -> None:
    """Test close event with minimize to tray enabled.

    Args:
        qtbot: PyQt test fixture
    """
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QSystemTrayIcon

    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True):
            window = MainWindow()
            qtbot.addWidget(window)
            window.minimize_to_tray = True
            window.show()

            event = QCloseEvent()
            window.closeEvent(event)

            # Event should be ignored, window hidden
            assert event.isAccepted() is False
            assert not window.isVisible()


def test_close_event_minimize_to_tray_disabled(qtbot: Any, window: MainWindow) -> None:
    """Test close event with minimize to tray disabled.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    window.minimize_to_tray = False
    window.show()

    event = QCloseEvent()
    with patch.object(QApplication, "quit"):
        window.closeEvent(event)

        # Event should be accepted
        assert event.isAccepted() is True


def test_close_event_minimize_to_tray_enabled_no_tray_icon(qtbot: Any) -> None:
    """Test close event with minimize to tray enabled but no tray icon.

    Args:
        qtbot: PyQt test fixture
    """
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            window = MainWindow()
            qtbot.addWidget(window)
            window.minimize_to_tray = True
            window.show()

            event = QCloseEvent()
            with patch.object(QApplication, "quit"):
                window.closeEvent(event)

                # Should quit instead of minimizing
                assert event.isAccepted() is True


def test_quit_application_stops_server(qtbot: Any, window: MainWindow) -> None:
    """Test quit application stops running server.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    from PySide6.QtWidgets import QApplication

    # Simulate running capture
    window.capture_panel.capturing = True

    with patch.object(window.capture_panel, "stop_capture") as mock_stop:
        with patch.object(QApplication, "quit"):
            window.quit_application()

            mock_stop.assert_called_once()


def test_quit_application_removes_qt_log_handlers(qtbot: Any, window: MainWindow) -> None:
    """Test quit application removes QtLogHandler instances.

    Args:
        qtbot: PyQt test fixture
        window (MainWindow): Window instance
    """
    import logging

    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler

    # Add a mock QtLogHandler
    root_logger = logging.getLogger()
    mock_handler = QtLogHandler()
    root_logger.addHandler(mock_handler)

    with patch.object(QApplication, "quit"):
        window.quit_application()

        # Handler should be removed
        assert mock_handler not in root_logger.handlers


def test_quit_application_hides_tray_icon(qtbot: Any) -> None:
    """Test quit application hides tray icon.

    Args:
        qtbot: PyQt test fixture
    """
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    with patch("foxhole_stockpiles.gui.widgets.capture_panel.LocalScanService"):
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True):
            window = MainWindow()
            qtbot.addWidget(window)

            with patch.object(window.tray_icon, "hide") as mock_hide:
                with patch.object(QApplication, "quit"):
                    window.quit_application()

                    mock_hide.assert_called_once()
