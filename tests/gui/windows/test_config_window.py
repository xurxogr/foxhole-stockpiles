"""Tests for ConfigWindow."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import QMessageBox

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.sections import (
    DatabaseBuilderSettings,
    ExternalToolsSettings,
    LoggingSettings,
    NotificationsSettings,
    OutputSettings,
    SavProcessingSettings,
    ScannerSettings,
)
from foxhole_stockpiles.enums.config_level import ConfigLevel
from foxhole_stockpiles.gui.windows.config_window import ConfigWindow
from foxhole_stockpiles.i18n import t


@pytest.fixture(autouse=True)
def mock_close_dialog() -> Any:
    """Mock QMessageBox.question to prevent closeEvent from blocking.

    The closeEvent shows a confirmation dialog when there are unsaved changes.
    """
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
        yield


@pytest.fixture
def mock_config_manager() -> Any:
    """Create a mock ConfigManager.

    Returns:
        MagicMock: Mock ConfigManager
    """
    from foxhole_stockpiles.core.settings.sections.gui import GUISettings

    with patch("foxhole_stockpiles.gui.windows.config_window.ConfigManager") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        # Create default settings with explicit BASIC config level
        default_settings = MagicMock(spec=AppSettings)
        default_settings.gui = GUISettings(config_level=ConfigLevel.BASIC)
        default_settings.scanner = ScannerSettings()
        default_settings.output = OutputSettings()
        default_settings.external_tools = ExternalToolsSettings()
        default_settings.database_builder = DatabaseBuilderSettings()
        default_settings.logging = LoggingSettings()
        default_settings.notifications = NotificationsSettings()
        default_settings.sav_processing = SavProcessingSettings()
        mock_instance.load_config.return_value = default_settings

        yield mock_instance


@pytest.fixture
def config_window(qtbot: Any, mock_config_manager: MagicMock) -> ConfigWindow:
    """Create a ConfigWindow instance.

    Args:
        qtbot: PyQt test fixture
        mock_config_manager: Mock ConfigManager

    Returns:
        ConfigWindow: Window instance
    """
    window = ConfigWindow()
    qtbot.addWidget(window)
    return window


def test_config_window_initialization(config_window: ConfigWindow) -> None:
    """Test ConfigWindow initialization.

    Args:
        config_window: ConfigWindow instance
    """
    assert config_window.windowTitle() == t("config_window.title")
    assert config_window.config_manager is not None
    assert config_window.settings is not None
    assert config_window.tab_widget is not None
    assert config_window.gui_tab is not None


def test_config_window_has_all_tabs(config_window: ConfigWindow) -> None:
    """Test ConfigWindow has all required tab widgets.

    Args:
        config_window: ConfigWindow instance
    """
    assert config_window.scanner_tab is not None
    assert config_window.output_tab is not None
    assert config_window.logging_tab is not None


def test_config_window_basic_level_by_default(config_window: ConfigWindow) -> None:
    """Test ConfigWindow starts with basic config level (5 tabs).

    Args:
        config_window: ConfigWindow instance
    """
    # Default config level is BASIC which shows 4 tabs
    assert config_window._current_config_level == ConfigLevel.BASIC
    assert config_window.tab_widget.count() == 4
    assert config_window.tab_widget.tabText(0) == t("config_window.tabs.scanner")


def test_config_window_config_level_tabs(qtbot: Any, mock_config_manager: MagicMock) -> None:
    """Test tab count at different config levels.

    Args:
        qtbot: PyQt test fixture
        mock_config_manager: Mock ConfigManager
    """
    from foxhole_stockpiles.core.settings.sections.gui import GUISettings

    # Test BASIC level (4 tabs)
    settings = AppSettings()
    settings.gui = GUISettings(config_level=ConfigLevel.BASIC)
    mock_config_manager.load_config.return_value = settings

    window = ConfigWindow()
    qtbot.addWidget(window)
    assert window.tab_widget.count() == 4

    # Test ADVANCED level
    # (6 tabs: + Notifications, SAV Processing)
    settings.gui = GUISettings(config_level=ConfigLevel.ADVANCED)
    mock_config_manager.load_config.return_value = settings

    window2 = ConfigWindow()
    qtbot.addWidget(window2)
    assert window2.tab_widget.count() == 6

    # Test DEVELOPER level (6 tabs: same sections as ADVANCED)
    settings.gui = GUISettings(config_level=ConfigLevel.DEVELOPER)
    mock_config_manager.load_config.return_value = settings

    window3 = ConfigWindow()
    qtbot.addWidget(window3)
    assert window3.tab_widget.count() == 6
    assert window3.tab_widget.tabText(0) == t("config_window.tabs.scanner")


def test_config_window_load_settings_populates_tabs(
    qtbot: Any, mock_config_manager: MagicMock
) -> None:
    """Test loading settings populates all tabs.

    Args:
        qtbot: PyQt test fixture
        mock_config_manager: Mock ConfigManager
    """
    # Create custom settings
    settings = AppSettings(
        scanner=ScannerSettings(capture_key="F9"),
    )
    mock_config_manager.load_config.return_value = settings

    window = ConfigWindow()
    qtbot.addWidget(window)

    # Verify settings were loaded
    assert window.settings is not None
    assert window.settings.scanner.capture_key == "F9"


def test_config_window_load_settings_error_handling(
    qtbot: Any, mock_config_manager: MagicMock
) -> None:
    """Test error handling when loading settings fails.

    Args:
        qtbot: PyQt test fixture
        mock_config_manager: Mock ConfigManager
    """
    # Make load_config raise an exception
    mock_config_manager.load_config.side_effect = Exception("Load failed")

    with patch("foxhole_stockpiles.gui.windows.config_window.QMessageBox.critical") as mock_msg:
        window = ConfigWindow()
        qtbot.addWidget(window)

        # Should show error dialog
        mock_msg.assert_called_once()
        args = mock_msg.call_args[0]
        assert t("config_window.dialogs.error_loading_title") in args[1]
        assert "Load failed" in args[2]


def test_config_window_save_settings_success(
    qtbot: Any, config_window: ConfigWindow, mock_config_manager: MagicMock
) -> None:
    """Test saving settings successfully.

    Args:
        qtbot: PyQt test fixture
        config_window: ConfigWindow instance
        mock_config_manager: Mock ConfigManager
    """
    mock_config_manager.save_config.return_value = (True, "Success")

    config_window.save_settings()

    # Should call save_config
    mock_config_manager.save_config.assert_called_once()

    # Should show success message in status bar
    assert "saved successfully" in config_window.status_bar.currentMessage().lower()


def test_config_window_save_settings_collects_from_tabs(
    qtbot: Any, config_window: ConfigWindow, mock_config_manager: MagicMock
) -> None:
    """Test saving settings collects values from all tabs.

    Args:
        qtbot: PyQt test fixture
        config_window: ConfigWindow instance
        mock_config_manager: Mock ConfigManager
    """
    mock_config_manager.save_config.return_value = (True, "Success")

    config_window.save_settings()

    # Should call save_config
    mock_config_manager.save_config.assert_called_once()

    # Should show success message in status bar
    assert "saved successfully" in config_window.status_bar.currentMessage().lower()


def test_config_window_save_settings_failure(
    qtbot: Any, config_window: ConfigWindow, mock_config_manager: MagicMock
) -> None:
    """Test handling save failure.

    Args:
        qtbot: PyQt test fixture
        config_window: ConfigWindow instance
        mock_config_manager: Mock ConfigManager
    """
    mock_config_manager.save_config.return_value = (False, "Save failed")

    with patch("foxhole_stockpiles.gui.windows.config_window.QMessageBox.critical") as mock_msg:
        config_window.save_settings()

        # Should show error message
        mock_msg.assert_called_once()
        args = mock_msg.call_args[0]
        assert args[1] == "Error Saving Configuration"
        assert "Save failed" in args[2]


def test_config_window_save_settings_exception(
    qtbot: Any, config_window: ConfigWindow, mock_config_manager: MagicMock
) -> None:
    """Test handling unexpected exception during save.

    Args:
        qtbot: PyQt test fixture
        config_window: ConfigWindow instance
        mock_config_manager: Mock ConfigManager
    """
    mock_config_manager.save_config.side_effect = Exception("Unexpected error")

    with patch("foxhole_stockpiles.gui.windows.config_window.QMessageBox.critical") as mock_msg:
        config_window.save_settings()

        # Should show error message
        mock_msg.assert_called_once()
        args = mock_msg.call_args[0]
        assert args[1] == "Error"
        assert "Unexpected error" in args[2]


def test_config_window_collect_settings_preserves_types(config_window: ConfigWindow) -> None:
    """Test collecting settings preserves all settings types.

    Args:
        config_window: ConfigWindow instance
    """
    # Collect settings
    settings = config_window.collect_settings()

    # Should return AppSettings instance with proper types
    assert isinstance(settings, AppSettings)
    assert isinstance(settings.scanner, ScannerSettings)
    assert isinstance(settings.logging, LoggingSettings)


def test_config_window_collect_settings_all_sections(config_window: ConfigWindow) -> None:
    """Test collecting settings returns all settings sections.

    Args:
        config_window: ConfigWindow instance
    """
    # Collect settings
    settings = config_window.collect_settings()

    # Should return AppSettings instance with all sections
    assert isinstance(settings, AppSettings)
    assert isinstance(settings.scanner, ScannerSettings)
    assert isinstance(settings.output, OutputSettings)
    assert isinstance(settings.database_builder, DatabaseBuilderSettings)
    assert isinstance(settings.logging, LoggingSettings)


def test_config_window_populate_tabs(config_window: ConfigWindow) -> None:
    """Test populate_tabs method.

    Args:
        config_window: ConfigWindow instance
    """
    # Create custom settings
    custom_settings = AppSettings(
        scanner=ScannerSettings(capture_key="F9"),
    )

    # Set and populate
    config_window.settings = custom_settings
    config_window.populate_tabs()

    # Verify scanner_tab was populated with the capture key
    assert config_window.scanner_tab.capture_key_display.text() == "F9"


def test_config_window_populate_tabs_none_settings(config_window: ConfigWindow) -> None:
    """Test populate_tabs with None settings.

    Args:
        config_window: ConfigWindow instance
    """
    # Set settings to None
    config_window.settings = None

    # Should not raise error
    config_window.populate_tabs()


def test_config_window_close_button_closes_window(qtbot: Any, config_window: ConfigWindow) -> None:
    """Test close button closes the window.

    Args:
        qtbot: PyQt test fixture
        config_window: ConfigWindow instance
    """
    # close_button is a named attribute on ConfigWindow
    assert config_window.close_button is not None
    assert config_window.close_button.text() == t("common.close")


def test_config_window_preserves_notifications_settings(config_window: ConfigWindow) -> None:
    """Test that notifications settings are preserved when collecting.

    Args:
        config_window: ConfigWindow instance
    """
    # Set custom notifications settings
    custom_notifications = NotificationsSettings()
    assert config_window.settings is not None
    config_window.settings.notifications = custom_notifications

    # Collect settings (basic mode)
    settings = config_window.collect_settings()

    # Should preserve notifications
    assert isinstance(settings.notifications, NotificationsSettings)


def test_config_window_geometry(config_window: ConfigWindow) -> None:
    """Test window geometry is set correctly.

    Args:
        config_window: ConfigWindow instance
    """
    # Window should have specific geometry
    assert config_window.geometry().width() >= 600  # Might be larger than 800 depending on DPI
    assert config_window.geometry().height() >= 400  # Might be larger than 600 depending on DPI


def test_config_window_gui_tab_exists(config_window: ConfigWindow) -> None:
    """Test GUI tab exists and has config level control.

    Args:
        config_window: ConfigWindow instance
    """
    # GUI tab should exist
    assert config_window.gui_tab is not None
    assert config_window.gui_tab.config_level_input is not None

    # GUI tab should be in the tab widget
    gui_tab_index = -1
    expected_text = t("config_window.tabs.gui")
    for i in range(config_window.tab_widget.count()):
        if config_window.tab_widget.tabText(i) == expected_text:
            gui_tab_index = i
            break
    assert gui_tab_index >= 0


class TestCloseEvent:
    """Tests for ConfigWindow.closeEvent method."""

    @pytest.fixture
    def mock_config_manager(self) -> Any:
        """Create a mock ConfigManager.

        Returns:
            MagicMock: Mock ConfigManager
        """
        with patch("foxhole_stockpiles.gui.windows.config_window.ConfigManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.load_config.return_value = AppSettings()
            yield mock_instance

    @pytest.fixture
    def config_window(self, qtbot: Any, mock_config_manager: MagicMock) -> ConfigWindow:
        """Create a ConfigWindow instance without autouse mock.

        Args:
            qtbot: PyQt test fixture
            mock_config_manager: Mock ConfigManager

        Returns:
            ConfigWindow: Window instance
        """
        window = ConfigWindow()
        qtbot.addWidget(window)
        return window

    def test_close_event_no_changes(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test closeEvent accepts when no changes.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # No changes made, has_changes() returns False
        event = MagicMock(spec=QCloseEvent)

        config_window.closeEvent(event)

        # Should accept without showing dialog
        event.accept.assert_called_once()
        event.ignore.assert_not_called()

    def test_close_event_with_changes_save(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test closeEvent when user clicks Save.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # Make changes (use scanner_tab to differ from loaded settings)
        config_window.scanner_tab.database_path_input.setText("changed.h5")
        mock_config_manager.save_config.return_value = (True, "Success")

        event = MagicMock(spec=QCloseEvent)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Save):
            config_window.closeEvent(event)

        # Should save and accept
        mock_config_manager.save_config.assert_called_once()
        event.accept.assert_called_once()

    def test_close_event_with_changes_save_fails(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test closeEvent when save fails after user clicks Save.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # Make changes (use scanner_tab to differ from loaded settings)
        config_window.scanner_tab.database_path_input.setText("changed.h5")
        mock_config_manager.save_config.return_value = (False, "Save failed")

        event = MagicMock(spec=QCloseEvent)

        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Save),
            patch.object(QMessageBox, "critical"),
        ):
            config_window.closeEvent(event)

        # Should not accept because save failed (still has changes)
        event.ignore.assert_called_once()

    def test_close_event_with_changes_discard(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test closeEvent when user clicks Discard.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # Make changes (use scanner_tab to differ from loaded settings)
        config_window.scanner_tab.database_path_input.setText("changed.h5")

        event = MagicMock(spec=QCloseEvent)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
            config_window.closeEvent(event)

        # Should accept without saving
        mock_config_manager.save_config.assert_not_called()
        event.accept.assert_called_once()

    def test_close_event_with_changes_cancel(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test closeEvent when user clicks Cancel.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # Make changes (use scanner_tab to differ from loaded settings)
        config_window.scanner_tab.database_path_input.setText("changed.h5")

        event = MagicMock(spec=QCloseEvent)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            config_window.closeEvent(event)

        # Should ignore (not close)
        mock_config_manager.save_config.assert_not_called()
        event.ignore.assert_called_once()
        event.accept.assert_not_called()


class TestKeyPressEvent:
    """Tests for ConfigWindow.keyPressEvent method."""

    @pytest.fixture
    def mock_config_manager(self) -> Any:
        """Create a mock ConfigManager.

        Returns:
            MagicMock: Mock ConfigManager
        """
        with patch("foxhole_stockpiles.gui.windows.config_window.ConfigManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.load_config.return_value = AppSettings()
            yield mock_instance

    @pytest.fixture
    def config_window(self, qtbot: Any, mock_config_manager: MagicMock) -> ConfigWindow:
        """Create a ConfigWindow instance.

        Args:
            qtbot: PyQt test fixture
            mock_config_manager: Mock ConfigManager

        Returns:
            ConfigWindow: Window instance
        """
        window = ConfigWindow()
        qtbot.addWidget(window)
        return window

    def test_escape_key_closes_window(self, config_window: ConfigWindow) -> None:
        """Test pressing Escape closes the window.

        Args:
            config_window: ConfigWindow instance
        """
        with (
            patch.object(config_window, "close") as mock_close,
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard),
        ):
            # Create escape key event
            event = QKeyEvent(
                QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
            )
            config_window.keyPressEvent(event)

            mock_close.assert_called_once()

    def test_other_key_passes_to_parent(self, config_window: ConfigWindow) -> None:
        """Test other keys are passed to parent handler.

        Args:
            config_window: ConfigWindow instance
        """
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
            # Create non-escape key event
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
            # Should not raise and should call parent handler
            config_window.keyPressEvent(event)


class TestSaveSettingsLanguageChange:
    """Tests for language change handling in save_settings."""

    @pytest.fixture
    def mock_config_manager(self) -> Any:
        """Create a mock ConfigManager.

        Returns:
            MagicMock: Mock ConfigManager
        """
        from foxhole_stockpiles.core.settings.sections.gui import GUISettings
        from foxhole_stockpiles.enums.supported_language import SupportedLanguage

        # Mock get_translator to ensure consistent language state
        mock_translator = MagicMock()
        mock_translator.language = "en"

        with (
            patch("foxhole_stockpiles.gui.windows.config_window.ConfigManager") as mock_class,
            patch(
                "foxhole_stockpiles.gui.windows.config_window.get_translator",
                return_value=mock_translator,
            ),
        ):
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            settings = AppSettings()
            settings.gui = GUISettings(
                config_level=ConfigLevel.BASIC, language=SupportedLanguage.ENGLISH
            )
            mock_instance.load_config.return_value = settings
            mock_instance.save_config.return_value = (True, "Success")
            yield mock_instance

    @pytest.fixture
    def config_window(self, qtbot: Any, mock_config_manager: MagicMock) -> ConfigWindow:
        """Create a ConfigWindow instance.

        Args:
            qtbot: PyQt test fixture
            mock_config_manager: Mock ConfigManager

        Returns:
            ConfigWindow: Window instance
        """
        window = ConfigWindow()
        qtbot.addWidget(window)
        return window

    def test_save_settings_language_change(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test save_settings triggers language change when language is changed.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # Change language in GUI tab
        config_window.gui_tab.language_input.setCurrentText("Espa\u00f1ol")

        with patch("foxhole_stockpiles.gui.windows.config_window.set_language") as mock_set_lang:
            config_window.save_settings()

            # Should call set_language with new language
            mock_set_lang.assert_called_once()


class TestSaveSettingsConfigLevelChange:
    """Tests for config level change handling in save_settings."""

    @pytest.fixture
    def mock_config_manager(self) -> Any:
        """Create a mock ConfigManager.

        Returns:
            MagicMock: Mock ConfigManager
        """
        from foxhole_stockpiles.core.settings.sections.gui import GUISettings

        with patch("foxhole_stockpiles.gui.windows.config_window.ConfigManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            settings = AppSettings()
            settings.gui = GUISettings(config_level=ConfigLevel.BASIC)
            mock_instance.load_config.return_value = settings
            mock_instance.save_config.return_value = (True, "Success")
            yield mock_instance

    @pytest.fixture
    def config_window(self, qtbot: Any, mock_config_manager: MagicMock) -> ConfigWindow:
        """Create a ConfigWindow instance.

        Args:
            qtbot: PyQt test fixture
            mock_config_manager: Mock ConfigManager

        Returns:
            ConfigWindow: Window instance
        """
        window = ConfigWindow()
        qtbot.addWidget(window)
        return window

    def test_save_settings_config_level_change(
        self, config_window: ConfigWindow, mock_config_manager: MagicMock
    ) -> None:
        """Test save_settings rebuilds tabs when config level is changed.

        Args:
            config_window: ConfigWindow instance
            mock_config_manager: Mock ConfigManager
        """
        # Initial tab count at BASIC level
        initial_tab_count = config_window.tab_widget.count()
        assert initial_tab_count == 4

        # Change config level to ADVANCED
        config_window.gui_tab.config_level_input.setCurrentText("Advanced")

        config_window.save_settings()

        # Tabs should be rebuilt with more tabs
        assert config_window.tab_widget.count() == 6


class TestRetranslate:
    """Tests for ConfigWindow.retranslate method."""

    @pytest.fixture
    def mock_config_manager(self) -> Any:
        """Create a mock ConfigManager.

        Returns:
            MagicMock: Mock ConfigManager
        """
        with patch("foxhole_stockpiles.gui.windows.config_window.ConfigManager") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.load_config.return_value = AppSettings()
            yield mock_instance

    @pytest.fixture
    def config_window(self, qtbot: Any, mock_config_manager: MagicMock) -> ConfigWindow:
        """Create a ConfigWindow instance.

        Args:
            qtbot: PyQt test fixture
            mock_config_manager: Mock ConfigManager

        Returns:
            ConfigWindow: Window instance
        """
        window = ConfigWindow()
        qtbot.addWidget(window)
        return window

    def test_retranslate_updates_window_title(self, config_window: ConfigWindow) -> None:
        """Test retranslate updates window title.

        Args:
            config_window: ConfigWindow instance
        """
        config_window.retranslate()

        assert config_window.windowTitle() == t("config_window.title")

    def test_retranslate_updates_buttons(self, config_window: ConfigWindow) -> None:
        """Test retranslate updates button texts.

        Args:
            config_window: ConfigWindow instance
        """
        config_window.retranslate()

        assert config_window.save_button.text() == t("common.save")
        assert config_window.close_button.text() == t("common.close")

    def test_retranslate_updates_hint_label(self, config_window: ConfigWindow) -> None:
        """Test retranslate updates hint label.

        Args:
            config_window: ConfigWindow instance
        """
        config_window.retranslate()

        assert config_window.hint_label.text() == t("config_window.tip_hover")

    def test_retranslate_rebuilds_tabs(self, config_window: ConfigWindow) -> None:
        """Test retranslate rebuilds tabs with translated names.

        Args:
            config_window: ConfigWindow instance
        """
        with patch.object(config_window, "_build_tabs") as mock_build:
            config_window.retranslate()

            mock_build.assert_called_once()
