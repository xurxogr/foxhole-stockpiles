"""Tests for IconImportWindow."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QMessageBox, QTableWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.sections.database_builder import DatabaseBuilderSettings
from foxhole_stockpiles.core.settings.sections.external_tools import ExternalToolsSettings
from foxhole_stockpiles.i18n import t
from fs_tools.gui.utils.icon_import_worker import IconImportWorker
from fs_tools.gui.windows.icon_import_window import IconImportWindow


# Prevent any GUI dialogs from appearing during test cleanup
@pytest.fixture(autouse=True)
def prevent_dialog_on_close() -> Generator[None, None, None]:
    """Prevent dialogs during window cleanup."""
    with patch(
        "fs_tools.gui.windows.icon_import_window.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        yield


@pytest.fixture
def mock_configured_settings(tmp_path: Path) -> AppSettings:
    """Create mock settings with proper configuration.

    Args:
        tmp_path: Temporary directory path

    Returns:
        AppSettings: Mock settings with all required tools configured
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("{}")

    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.write_text("")

    converter_tool = tmp_path / "umodel.exe"
    converter_tool.write_text("")

    return AppSettings(
        external_tools=ExternalToolsSettings(
            repak=extractor_tool,
            umodel=converter_tool,
        ),
        database_builder=DatabaseBuilderSettings(
            catalog_file=catalog_file,
        ),
    )


@pytest.fixture
def mock_unconfigured_settings() -> AppSettings:
    """Create mock settings without configuration.

    Returns:
        AppSettings: Mock settings with missing tools
    """
    return AppSettings(
        external_tools=ExternalToolsSettings(),
        database_builder=DatabaseBuilderSettings(),
    )


@pytest.fixture
def configured_window(
    qtbot: Any, mock_configured_settings: AppSettings
) -> Generator[IconImportWindow, None, None]:
    """Create a configured IconImportWindow instance.

    Args:
        qtbot: PyQt test fixture
        mock_configured_settings: Mock configured settings

    Yields:
        IconImportWindow: Window instance
    """
    with patch(
        "fs_tools.gui.windows.icon_import_window.get_settings",
        return_value=mock_configured_settings,
    ):
        window = IconImportWindow()
        qtbot.addWidget(window)
        yield window
        # Cleanup: stop any running workers
        if window.import_worker and window.import_worker.isRunning():
            window.import_worker.stop()
            window.import_worker.wait()


@pytest.fixture
def unconfigured_window(
    qtbot: Any, mock_unconfigured_settings: AppSettings
) -> Generator[IconImportWindow, None, None]:
    """Create an unconfigured IconImportWindow instance.

    Args:
        qtbot: PyQt test fixture
        mock_unconfigured_settings: Mock unconfigured settings

    Yields:
        IconImportWindow: Window instance
    """
    with patch(
        "fs_tools.gui.windows.icon_import_window.get_settings",
        return_value=mock_unconfigured_settings,
    ):
        window = IconImportWindow()
        qtbot.addWidget(window)
        yield window
        # Cleanup: stop any running workers
        if window.import_worker and window.import_worker.isRunning():
            window.import_worker.stop()
            window.import_worker.wait()


# ===== Initialization Tests =====


def test_icon_import_window_initialization_configured(configured_window: IconImportWindow) -> None:
    """Test IconImportWindow initialization when configured.

    Args:
        configured_window: Configured window instance
    """
    assert configured_window.windowTitle() == t("database_builder.title")
    assert configured_window.is_configured is True
    assert configured_window.import_worker is None
    assert configured_window.mod_pak_files == []
    assert configured_window.vanilla_pak_file is None
    assert configured_window.log_handler is not None


def test_icon_import_window_initialization_unconfigured(
    unconfigured_window: IconImportWindow,
) -> None:
    """Test IconImportWindow initialization when not configured.

    Args:
        unconfigured_window: Unconfigured window instance
    """
    assert unconfigured_window.windowTitle() == t("database_builder.title")
    assert unconfigured_window.is_configured is False


def test_icon_import_window_widgets_exist(configured_window: IconImportWindow) -> None:
    """Test that all required widgets exist.

    Args:
        configured_window: Configured window instance
    """
    assert configured_window.vanilla_pak_display is not None
    assert configured_window.mod_pak_list_widget is not None
    assert configured_window.mod_name_input is not None
    assert configured_window.overwrite_checkbox is not None
    assert configured_window.start_button is not None
    assert configured_window.cancel_button is not None
    assert configured_window.log_display is not None


def test_icon_import_window_cancel_button_disabled(configured_window: IconImportWindow) -> None:
    """Test cancel button is disabled initially.

    Args:
        configured_window: Configured window instance
    """
    assert configured_window.cancel_button.isEnabled() is False


# ===== Configuration Check Tests =====


def test_check_configuration_all_present(qtbot: Any, tmp_path: Path) -> None:
    """Test configuration check when all tools are present.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("{}")

    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.write_text("")

    converter_tool = tmp_path / "umodel.exe"
    converter_tool.write_text("")

    settings = AppSettings(
        external_tools=ExternalToolsSettings(
            repak=extractor_tool,
            umodel=converter_tool,
        ),
        database_builder=DatabaseBuilderSettings(
            catalog_file=catalog_file,
        ),
    )

    with patch("fs_tools.gui.windows.icon_import_window.get_settings", return_value=settings):
        window = IconImportWindow()
        qtbot.addWidget(window)
        assert window._check_configuration() is True


def test_check_configuration_missing_extractor(qtbot: Any, tmp_path: Path) -> None:
    """Test configuration check when extractor tool is missing.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("{}")

    converter_tool = tmp_path / "umodel.exe"
    converter_tool.write_text("")

    settings = AppSettings(
        external_tools=ExternalToolsSettings(
            repak=None,
            umodel=converter_tool,
        ),
        database_builder=DatabaseBuilderSettings(
            catalog_file=catalog_file,
        ),
    )

    with patch("fs_tools.gui.windows.icon_import_window.get_settings", return_value=settings):
        window = IconImportWindow()
        qtbot.addWidget(window)
        assert window._check_configuration() is False


def test_check_configuration_missing_converter(qtbot: Any, tmp_path: Path) -> None:
    """Test configuration check when converter tool is missing.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("{}")

    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.write_text("")

    settings = AppSettings(
        external_tools=ExternalToolsSettings(
            repak=extractor_tool,
            umodel=None,
        ),
        database_builder=DatabaseBuilderSettings(
            catalog_file=catalog_file,
        ),
    )

    with patch("fs_tools.gui.windows.icon_import_window.get_settings", return_value=settings):
        window = IconImportWindow()
        qtbot.addWidget(window)
        assert window._check_configuration() is False


def test_check_configuration_missing_catalog(qtbot: Any, tmp_path: Path) -> None:
    """Test configuration check when catalog file is missing.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.write_text("")

    converter_tool = tmp_path / "umodel.exe"
    converter_tool.write_text("")

    settings = AppSettings(
        external_tools=ExternalToolsSettings(
            repak=extractor_tool,
            umodel=converter_tool,
        ),
        database_builder=DatabaseBuilderSettings(
            catalog_file=None,
        ),
    )

    with patch("fs_tools.gui.windows.icon_import_window.get_settings", return_value=settings):
        window = IconImportWindow()
        qtbot.addWidget(window)
        assert window._check_configuration() is False


def test_check_configuration_file_not_exists(qtbot: Any, tmp_path: Path) -> None:
    """Test configuration check when files don't exist.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    settings = AppSettings(
        external_tools=ExternalToolsSettings(
            repak=Path("/nonexistent/repak.exe"),
            umodel=Path("/nonexistent/umodel.exe"),
        ),
        database_builder=DatabaseBuilderSettings(
            catalog_file=Path("/nonexistent/catalog.json"),
        ),
    )

    with patch("fs_tools.gui.windows.icon_import_window.get_settings", return_value=settings):
        window = IconImportWindow()
        qtbot.addWidget(window)
        assert window._check_configuration() is False


# ===== PAK File Management Tests =====


def test_add_mod_pak_files(qtbot: Any, configured_window: IconImportWindow, tmp_path: Path) -> None:
    """Test adding PAK files via file dialog.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_pak1 = str(tmp_path / "test1.pak")
    test_pak2 = str(tmp_path / "test2.pak")

    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getOpenFileNames"
    ) as mock_dialog:
        mock_dialog.return_value = ([test_pak1, test_pak2], "PAK Files (*.pak)")

        # Mock validation to prevent background thread issues
        with patch.object(configured_window, "_trigger_validation"):
            configured_window.add_mod_pak_files()

        assert configured_window.mod_pak_files == [test_pak1, test_pak2]
        assert configured_window.mod_pak_list_widget.count() == 2
        item0 = configured_window.mod_pak_list_widget.item(0)
        item1 = configured_window.mod_pak_list_widget.item(1)
        assert item0 is not None and item0.text() == test_pak1
        assert item1 is not None and item1.text() == test_pak2


def test_add_mod_pak_files_no_duplicates(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test adding duplicate PAK files doesn't duplicate entries.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_pak = str(tmp_path / "test.pak")

    with patch.object(configured_window, "_trigger_validation"):
        # Add once
        with patch(
            "fs_tools.gui.windows.icon_import_window.QFileDialog.getOpenFileNames"
        ) as mock_dialog:
            mock_dialog.return_value = ([test_pak], "PAK Files (*.pak)")
            configured_window.add_mod_pak_files()

        # Try to add again
        with patch(
            "fs_tools.gui.windows.icon_import_window.QFileDialog.getOpenFileNames"
        ) as mock_dialog:
            mock_dialog.return_value = ([test_pak], "PAK Files (*.pak)")
            configured_window.add_mod_pak_files()

    # Should still be only one entry
    assert len(configured_window.mod_pak_files) == 1
    assert configured_window.mod_pak_list_widget.count() == 1


def test_add_mod_pak_files_cancel(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test canceling add PAK files dialog.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getOpenFileNames"
    ) as mock_dialog:
        mock_dialog.return_value = ([], "")

        configured_window.add_mod_pak_files()

        assert configured_window.mod_pak_files == []
        assert configured_window.mod_pak_list_widget.count() == 0


def test_remove_selected_paks(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test removing selected PAK files.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_pak1 = str(tmp_path / "test1.pak")
    test_pak2 = str(tmp_path / "test2.pak")

    # Add files
    configured_window.mod_pak_files = [test_pak1, test_pak2]
    configured_window.mod_pak_list_widget.addItem(test_pak1)
    configured_window.mod_pak_list_widget.addItem(test_pak2)

    # Select first item
    item0 = configured_window.mod_pak_list_widget.item(0)
    assert item0 is not None
    item0.setSelected(True)

    # Remove (mock validation)
    with patch.object(configured_window, "_trigger_validation"):
        configured_window.remove_selected_mod_paks()

    # Only second should remain
    assert configured_window.mod_pak_files == [test_pak2]
    assert configured_window.mod_pak_list_widget.count() == 1
    remaining_item = configured_window.mod_pak_list_widget.item(0)
    assert remaining_item is not None and remaining_item.text() == test_pak2


def test_clear_all_paks(qtbot: Any, configured_window: IconImportWindow, tmp_path: Path) -> None:
    """Test clearing all PAK files.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_pak1 = str(tmp_path / "test1.pak")
    test_pak2 = str(tmp_path / "test2.pak")

    # Add files
    configured_window.mod_pak_files = [test_pak1, test_pak2]
    configured_window.mod_pak_list_widget.addItem(test_pak1)
    configured_window.mod_pak_list_widget.addItem(test_pak2)

    # Clear
    configured_window.clear_all_mod_paks()

    assert configured_window.mod_pak_files == []
    assert configured_window.mod_pak_list_widget.count() == 0


# ===== Drag and Drop Tests =====


def test_pak_drag_enter_event(configured_window: IconImportWindow) -> None:
    """Test drag enter event accepts drags.

    Args:
        configured_window: Configured window instance
    """
    mock_event = MagicMock(spec=QDragEnterEvent)
    configured_window.pak_drag_enter_event(mock_event)
    mock_event.accept.assert_called_once()


def test_pak_drag_enter_event_none(configured_window: IconImportWindow) -> None:
    """Test drag enter event with None event.

    Args:
        configured_window: Configured window instance
    """
    # Should not raise exception
    configured_window.pak_drag_enter_event(None)


def test_pak_drop_event(configured_window: IconImportWindow, tmp_path: Path) -> None:
    """Test drop event adds PAK files.

    Args:
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_pak = str(tmp_path / "test.pak")

    # Create mock drop event
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(test_pak)])

    mock_event = MagicMock(spec=QDropEvent)
    mock_event.mimeData.return_value = mime_data

    with patch.object(configured_window, "_trigger_validation"):
        configured_window.pak_drop_event(mock_event)

    assert test_pak in configured_window.mod_pak_files
    assert configured_window.mod_pak_list_widget.count() == 1
    mock_event.accept.assert_called_once()


def test_pak_drop_event_non_pak_file(configured_window: IconImportWindow, tmp_path: Path) -> None:
    """Test drop event ignores non-PAK files.

    Args:
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_txt = str(tmp_path / "test.txt")

    # Create mock drop event
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(test_txt)])

    mock_event = MagicMock(spec=QDropEvent)
    mock_event.mimeData.return_value = mime_data

    configured_window.pak_drop_event(mock_event)

    assert configured_window.mod_pak_files == []
    assert configured_window.mod_pak_list_widget.count() == 0


def test_pak_drop_event_none(configured_window: IconImportWindow) -> None:
    """Test drop event with None event.

    Args:
        configured_window: Configured window instance
    """
    # Should not raise exception
    configured_window.pak_drop_event(None)


# ===== Validation Tests =====


def test_validate_inputs_no_mod_pak_files(configured_window: IconImportWindow) -> None:
    """Test validation fails when no mod PAK files are added.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_name_input.setText("test_mod")

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.add_pak_file")


def test_validate_inputs_no_mod_name(configured_window: IconImportWindow) -> None:
    """Test validation fails when mod name is empty.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.enter_mod_name")


def test_validate_inputs_valid(configured_window: IconImportWindow) -> None:
    """Test validation succeeds with valid inputs.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window.db_path_input.setText("/tmp/test.h5")

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is True
    assert error_msg == ""


# ===== Import Process Tests =====


def test_start_import_validation_fails(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test start import shows warning when validation fails.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    with patch("fs_tools.gui.windows.icon_import_window.QMessageBox.warning") as mock_warning:
        configured_window.start_import()

        mock_warning.assert_called_once()
        args = mock_warning.call_args[0]
        assert args[1] == t("common.validation_error")


def test_start_import_success(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test successful start of import process.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window.db_path_input.setText("/tmp/test.h5")

    with patch("fs_tools.gui.windows.icon_import_window.IconImportWorker") as mock_worker_class:
        mock_worker = MagicMock(spec=IconImportWorker)
        mock_worker_class.return_value = mock_worker

        configured_window.start_import()

        # Worker should be created and started
        assert configured_window.import_worker is not None
        mock_worker.start.assert_called_once()

        # Buttons should be updated
        assert configured_window.start_button.isEnabled() is False
        assert configured_window.cancel_button.isEnabled() is True
        assert configured_window.mod_name_input.isEnabled() is False


def test_start_import_no_catalog(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test start import when catalog file is not configured.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window.db_path_input.setText("/tmp/test.h5")
    configured_window.settings.database_builder.catalog_file = None

    with patch(
        "fs_tools.gui.windows.icon_import_window.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        with patch("fs_tools.gui.windows.icon_import_window.QMessageBox.critical") as mock_critical:
            configured_window.start_import()

            mock_critical.assert_called_once()
            args = mock_critical.call_args[0]
            assert "Catalog file not configured" in args[2]


def test_cancel_import_not_running(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test cancel import when worker is not running.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Should not raise exception
    configured_window.cancel_import()


def test_cancel_import_user_confirms(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test cancel import when user confirms.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Create mock worker
    mock_worker = MagicMock(spec=IconImportWorker)
    mock_worker.isRunning.return_value = True
    configured_window.import_worker = mock_worker

    with patch(
        "fs_tools.gui.windows.icon_import_window.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        configured_window.cancel_import()

        mock_worker.stop.assert_called_once()
        mock_worker.wait.assert_called_once()


def test_on_import_finished_success(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test import finished handler on success.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Disable buttons as if import was running
    configured_window.start_button.setEnabled(False)
    configured_window.cancel_button.setEnabled(True)
    configured_window.mod_name_input.setEnabled(False)
    configured_window.overwrite_checkbox.setEnabled(False)

    # Clear logs before test
    configured_window.clear_logs()

    configured_window.on_import_finished(True)

    # Buttons should be re-enabled
    assert configured_window.start_button.isEnabled() is True
    assert configured_window.cancel_button.isEnabled() is False
    assert configured_window.mod_name_input.isEnabled() is True
    assert configured_window.overwrite_checkbox.isEnabled() is True

    # Should add success log message
    assert configured_window.log_display.rowCount() == 1
    message_item = configured_window.log_display.item(0, 3)
    assert (
        message_item is not None and t("database_builder.import_completed") in message_item.text()
    )


def test_on_import_finished_failure(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test import finished handler on failure.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Disable buttons as if import was running
    configured_window.start_button.setEnabled(False)
    configured_window.cancel_button.setEnabled(True)

    configured_window.on_import_finished(False)

    # Buttons should be re-enabled
    assert configured_window.start_button.isEnabled() is True
    assert configured_window.cancel_button.isEnabled() is False


def test_on_import_error(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test import error handler.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Clear logs before test
    configured_window.clear_logs()

    configured_window.on_import_error("Test error message")

    # Should add error log message
    assert configured_window.log_display.rowCount() == 1
    level_item = configured_window.log_display.item(0, 1)
    message_item = configured_window.log_display.item(0, 3)
    assert level_item is not None and level_item.text() == "ERROR"
    assert message_item is not None and "Test error message" in message_item.text()


# ===== Log Display Tests =====


def test_append_log(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test appending log entries.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    log_data = {
        "timestamp": "12:00:00",
        "level": "INFO",
        "module": "test_module",
        "message": "Test message",
        "color": "#FFFFFF",
    }

    configured_window.append_log(log_data)

    assert configured_window.log_display.rowCount() == 1
    item_0_0 = configured_window.log_display.item(0, 0)
    item_0_1 = configured_window.log_display.item(0, 1)
    item_0_2 = configured_window.log_display.item(0, 2)
    item_0_3 = configured_window.log_display.item(0, 3)
    assert item_0_0 is not None and item_0_0.text() == "12:00:00"
    assert item_0_1 is not None and item_0_1.text() == "INFO"
    assert item_0_2 is not None and item_0_2.text() == "test_module"
    assert item_0_3 is not None and item_0_3.text() == "Test message"


def test_append_multiple_logs(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test appending multiple log entries.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    log1 = {
        "timestamp": "12:00:00",
        "level": "INFO",
        "module": "module1",
        "message": "Message 1",
        "color": "#FFFFFF",
    }
    log2 = {
        "timestamp": "12:00:01",
        "level": "ERROR",
        "module": "module2",
        "message": "Message 2",
        "color": "#FF0000",
    }

    configured_window.append_log(log1)
    configured_window.append_log(log2)

    assert configured_window.log_display.rowCount() == 2


def test_clear_logs(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test clearing log entries.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Add some logs
    log_data = {
        "timestamp": "12:00:00",
        "level": "INFO",
        "module": "test_module",
        "message": "Test message",
        "color": "#FFFFFF",
    }
    configured_window.append_log(log_data)
    configured_window.append_log(log_data)

    assert configured_window.log_display.rowCount() == 2

    # Clear
    configured_window.clear_logs()

    assert configured_window.log_display.rowCount() == 0


# ===== Close Event Tests =====


def test_close_event_no_worker(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test close event when no worker is running.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    mock_event = MagicMock()

    configured_window.closeEvent(mock_event)

    mock_event.accept.assert_called_once()
    mock_event.ignore.assert_not_called()


def test_close_event_worker_not_running(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test close event when worker exists but is not running.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    mock_worker = MagicMock(spec=IconImportWorker)
    mock_worker.isRunning.return_value = False
    configured_window.import_worker = mock_worker

    mock_event = MagicMock()

    configured_window.closeEvent(mock_event)

    mock_event.accept.assert_called_once()
    mock_event.ignore.assert_not_called()


def test_close_event_worker_running_user_confirms(
    qtbot: Any, configured_window: IconImportWindow
) -> None:
    """Test close event when worker is running and user confirms.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    mock_worker = MagicMock(spec=IconImportWorker)
    mock_worker.isRunning.return_value = True
    configured_window.import_worker = mock_worker

    mock_event = MagicMock()

    with patch(
        "fs_tools.gui.windows.icon_import_window.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        configured_window.closeEvent(mock_event)

        mock_worker.stop.assert_called_once()
        mock_worker.wait.assert_called_once()
        mock_event.accept.assert_called_once()
        mock_event.ignore.assert_not_called()


def test_close_event_worker_running_user_declines(
    qtbot: Any, configured_window: IconImportWindow
) -> None:
    """Test close event when worker is running and user declines.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    mock_worker = MagicMock(spec=IconImportWorker)
    mock_worker.isRunning.return_value = True
    configured_window.import_worker = mock_worker

    mock_event = MagicMock()

    with patch("fs_tools.gui.windows.icon_import_window.QMessageBox.question") as mock_question:
        mock_question.return_value = QMessageBox.StandardButton.No

        configured_window.closeEvent(mock_event)

        mock_worker.stop.assert_not_called()
        mock_event.accept.assert_not_called()
        mock_event.ignore.assert_called_once()


# ===== Additional Coverage Tests =====


def test_start_import_invalid_mod_name(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test start import with invalid mod name.

    Verifies that inputs are re-enabled after validation error so user can fix the mod name.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("invalid/mod<name>")  # Invalid characters
    configured_window.db_path_input.setText("/tmp/test.h5")  # pass earlier validation

    with patch("fs_tools.gui.windows.icon_import_window.QMessageBox.critical") as mock_critical:
        configured_window.start_import()

        mock_critical.assert_called_once()
        assert t("database_builder.invalid_mod_name_title") in str(mock_critical.call_args)
        assert configured_window.import_worker is None

        # Verify inputs are re-enabled so user can fix the error
        assert configured_window.mod_name_input.isEnabled() is True
        assert configured_window.workers_spinbox.isEnabled() is True
        assert configured_window.db_path_input.isEnabled() is True
        assert configured_window.overwrite_checkbox.isEnabled() is True
        assert configured_window.start_button.isEnabled() is True
        assert configured_window.cancel_button.isEnabled() is False


def test_clear_vanilla_pak(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test clearing vanilla PAK selection.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    configured_window.vanilla_pak_file = "test.pak"
    configured_window.vanilla_pak_display.setText("test.pak")

    configured_window.clear_vanilla_pak()

    assert configured_window.vanilla_pak_file is None
    assert configured_window.vanilla_pak_display.text() == ""


def test_copy_selected_logs(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test copying selected log rows to clipboard.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    # Add some log entries
    configured_window.append_log(
        {
            "timestamp": "2024-01-01 12:00:00",
            "level": "INFO",
            "module": "test.module",
            "message": "Test message 1",
            "color": "#FFFFFF",
        }
    )
    configured_window.append_log(
        {
            "timestamp": "2024-01-01 12:00:01",
            "level": "ERROR",
            "module": "test.module",
            "message": "Test message 2",
            "color": "#FF0000",
        }
    )

    # Select all rows
    configured_window.log_display.selectAll()

    with patch("fs_tools.gui.windows.icon_import_window.QApplication.clipboard") as mock_clipboard:
        mock_clipboard_instance = MagicMock()
        mock_clipboard.return_value = mock_clipboard_instance

        configured_window._copy_selected_logs()

        # Check clipboard was called with formatted text
        mock_clipboard_instance.setText.assert_called_once()
        clipboard_text = mock_clipboard_instance.setText.call_args[0][0]
        assert "[2024-01-01 12:00:00] INFO test.module: Test message 1" in clipboard_text
        assert "[2024-01-01 12:00:01] ERROR test.module: Test message 2" in clipboard_text


# ===== QFileDialog Tests =====


def test_select_vanilla_pak_file_selected(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test selecting a vanilla PAK file via dialog.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_pak = str(tmp_path / "FoxholeVanilla.pak")

    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_pak, "PAK Files (*.pak)")

        with patch.object(configured_window, "_trigger_vanilla_validation"):
            configured_window.select_vanilla_pak()

        assert configured_window.vanilla_pak_file == test_pak
        assert configured_window.vanilla_pak_display.text() == test_pak


def test_select_vanilla_pak_cancelled(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test cancelling vanilla PAK file dialog.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        configured_window.select_vanilla_pak()

        assert configured_window.vanilla_pak_file is None
        assert configured_window.vanilla_pak_display.text() == ""


def test_select_database_path_file_selected(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test selecting a database path via dialog.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_db = str(tmp_path / "database.h5")

    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_db, "HDF5 Database (*.h5)")

        configured_window.select_database_path()

        assert configured_window.db_path_input.text() == test_db


def test_select_database_path_adds_h5_extension(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test that .h5 extension is added if missing.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    test_db = str(tmp_path / "database")  # No extension

    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_db, "HDF5 Database (*.h5)")

        configured_window.select_database_path()

        assert configured_window.db_path_input.text() == test_db + ".h5"


def test_select_database_path_cancelled(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test cancelling database path dialog.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    original_text = configured_window.db_path_input.text()

    with patch(
        "fs_tools.gui.windows.icon_import_window.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        configured_window.select_database_path()

        # Should not change the current value
        assert configured_window.db_path_input.text() == original_text


def test_validate_inputs_no_db_path(configured_window: IconImportWindow) -> None:
    """Test validation fails when database path is empty.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window.db_path_input.setText("")

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.select_database")


# ===== Platform-Specific Path Tests =====


def test_get_default_pak_directory_windows(configured_window: IconImportWindow) -> None:
    """Test default PAK directory on Windows when Steam path exists.

    Args:
        configured_window: Configured window instance
    """
    steam_path = "C:/Program Files (x86)/Steam/steamapps/common/Foxhole/War/Content/Paks"

    with (
        patch("fs_tools.gui.windows.icon_import_window.platform.system") as mock_system,
        patch("fs_tools.gui.windows.icon_import_window.Path") as mock_path_class,
    ):
        mock_system.return_value = "Windows"

        # Mock Path.cwd() to return a default path
        mock_cwd = MagicMock()
        mock_path_class.cwd.return_value = mock_cwd

        # Mock the Steam path to exist
        mock_steam_path = MagicMock()
        mock_steam_path.exists.return_value = True
        mock_steam_path.__str__ = MagicMock(return_value=steam_path)  # type: ignore[method-assign]

        # Make Path() return different mocks based on the argument
        def path_constructor(arg: str) -> MagicMock:
            if "Steam" in arg:
                return mock_steam_path
            return mock_cwd

        mock_path_class.side_effect = path_constructor

        result = configured_window._get_default_pak_directory()

        assert result == steam_path


def test_get_default_pak_directory_windows_no_steam(configured_window: IconImportWindow) -> None:
    """Test default PAK directory on Windows when Steam path doesn't exist.

    Args:
        configured_window: Configured window instance
    """
    with (
        patch("fs_tools.gui.windows.icon_import_window.platform.system") as mock_system,
        patch("fs_tools.gui.windows.icon_import_window.Path") as mock_path_class,
    ):
        mock_system.return_value = "Windows"

        # Mock Path.cwd() to return a default path
        mock_cwd = MagicMock()
        mock_cwd.__str__ = MagicMock(return_value="/home/user")  # type: ignore[method-assign]
        mock_path_class.cwd.return_value = mock_cwd

        # Mock the Steam path to not exist
        mock_steam_path = MagicMock()
        mock_steam_path.exists.return_value = False

        def path_constructor(arg: str) -> MagicMock:
            if "Steam" in arg:
                return mock_steam_path
            return mock_cwd

        mock_path_class.side_effect = path_constructor

        result = configured_window._get_default_pak_directory()

        assert result == "/home/user"


def test_get_default_pak_directory_wsl(configured_window: IconImportWindow) -> None:
    """Test default PAK directory on WSL when path exists.

    Args:
        configured_window: Configured window instance
    """
    wsl_path = "/mnt/c/Program Files (x86)/Steam/steamapps/common/Foxhole/War/Content/Paks"

    with (
        patch("fs_tools.gui.windows.icon_import_window.platform.system") as mock_system,
        patch("fs_tools.gui.windows.icon_import_window.Path") as mock_path_class,
        patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(
                    __enter__=lambda self: MagicMock(
                        read=lambda: "Linux version microsoft-standard-WSL2"
                    ),
                    __exit__=lambda *args: None,
                )
            ),
        ),
    ):
        mock_system.return_value = "Linux"

        # Mock Path.cwd()
        mock_cwd = MagicMock()
        mock_path_class.cwd.return_value = mock_cwd

        # Mock the WSL path to exist
        mock_wsl_path = MagicMock()
        mock_wsl_path.exists.return_value = True
        mock_wsl_path.__str__ = MagicMock(return_value=wsl_path)  # type: ignore[method-assign]

        def path_constructor(arg: str) -> MagicMock:
            if "/mnt/c" in arg:
                return mock_wsl_path
            return mock_cwd

        mock_path_class.side_effect = path_constructor

        result = configured_window._get_default_pak_directory()

        assert result == wsl_path


def test_get_default_pak_directory_linux_not_wsl(configured_window: IconImportWindow) -> None:
    """Test default PAK directory on native Linux.

    Args:
        configured_window: Configured window instance
    """
    with (
        patch("fs_tools.gui.windows.icon_import_window.platform.system") as mock_system,
        patch("fs_tools.gui.windows.icon_import_window.Path") as mock_path_class,
        patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(
                    __enter__=lambda self: MagicMock(read=lambda: "Linux version 6.1.0-generic"),
                    __exit__=lambda *args: None,
                )
            ),
        ),
    ):
        mock_system.return_value = "Linux"

        # Mock Path.cwd()
        mock_cwd = MagicMock()
        mock_cwd.__str__ = MagicMock(return_value="/home/user")  # type: ignore[method-assign]
        mock_path_class.cwd.return_value = mock_cwd

        result = configured_window._get_default_pak_directory()

        assert result == "/home/user"


def test_get_default_pak_directory_linux_oserror(configured_window: IconImportWindow) -> None:
    """Test default PAK directory on Linux when /proc/version can't be read.

    Args:
        configured_window: Configured window instance
    """
    with (
        patch("fs_tools.gui.windows.icon_import_window.platform.system") as mock_system,
        patch("fs_tools.gui.windows.icon_import_window.Path") as mock_path_class,
        patch("builtins.open", side_effect=OSError("Permission denied")),
    ):
        mock_system.return_value = "Linux"

        # Mock Path.cwd()
        mock_cwd = MagicMock()
        mock_cwd.__str__ = MagicMock(return_value="/home/user")  # type: ignore[method-assign]
        mock_path_class.cwd.return_value = mock_cwd

        result = configured_window._get_default_pak_directory()

        assert result == "/home/user"


def test_get_default_pak_directory_macos(configured_window: IconImportWindow) -> None:
    """Test default PAK directory on macOS (unsupported platform).

    Args:
        configured_window: Configured window instance
    """
    with (
        patch("fs_tools.gui.windows.icon_import_window.platform.system") as mock_system,
        patch("fs_tools.gui.windows.icon_import_window.Path") as mock_path_class,
    ):
        mock_system.return_value = "Darwin"

        # Mock Path.cwd()
        mock_cwd = MagicMock()
        mock_cwd.__str__ = MagicMock(return_value="/Users/user")  # type: ignore[method-assign]
        mock_path_class.cwd.return_value = mock_cwd

        result = configured_window._get_default_pak_directory()

        assert result == "/Users/user"


# ===== PAK Validation Tests =====


def test_trigger_validation_no_pak_files(configured_window: IconImportWindow) -> None:
    """Test _trigger_validation does nothing when no PAK files.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = []

    with patch.object(configured_window, "_set_pak_controls_enabled") as mock_set:
        configured_window._trigger_validation()
        mock_set.assert_not_called()


def test_trigger_validation_no_extractor_tool(
    qtbot: Any, mock_unconfigured_settings: AppSettings
) -> None:
    """Test _trigger_validation does nothing when extractor not configured.

    Args:
        qtbot: PyQt test fixture
        mock_unconfigured_settings: Mock unconfigured settings
    """
    with patch(
        "fs_tools.gui.windows.icon_import_window.get_settings",
        return_value=mock_unconfigured_settings,
    ):
        window = IconImportWindow()
        qtbot.addWidget(window)

        window.mod_pak_files = ["test.pak"]

        with patch.object(window, "_set_pak_controls_enabled") as mock_set:
            window._trigger_validation()
            mock_set.assert_not_called()


def test_trigger_validation_starts_worker(qtbot: Any, configured_window: IconImportWindow) -> None:
    """Test _trigger_validation starts a validation worker.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]

    with patch("fs_tools.gui.windows.icon_import_window.PakValidationWorker") as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        mock_worker_class.return_value = mock_worker

        configured_window._trigger_validation()

        mock_worker_class.assert_called_once()
        mock_worker.validation_complete.connect.assert_called_once()
        mock_worker.start.assert_called_once()
        assert configured_window._is_validating is True


def test_on_validation_complete_valid(configured_window: IconImportWindow) -> None:
    """Test _on_validation_complete when validation passes.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    result = PakValidationResult()
    result.is_valid = True
    result.has_crate_icon = True
    result.has_subicons = True
    result.subicons_count = 10

    configured_window._is_validating = True
    configured_window.vanilla_group.setVisible(True)

    configured_window._on_validation_complete(result)

    assert configured_window._is_validating is False
    assert configured_window._validation_result == result
    # Use isHidden() since window isn't shown
    assert configured_window.vanilla_group.isHidden() is True
    assert (
        t("database_builder.validation.all_assets_found")
        in configured_window.validation_status_label.text()
    )


def test_on_validation_complete_missing_crate(configured_window: IconImportWindow) -> None:
    """Test _on_validation_complete when crate icon is missing.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    result = PakValidationResult()
    result.is_valid = False
    result.has_crate_icon = False
    result.has_subicons = True
    result.subicons_count = 10

    configured_window._is_validating = True
    configured_window.vanilla_group.setVisible(False)

    configured_window._on_validation_complete(result)

    assert configured_window._is_validating is False
    # Use isHidden() since window isn't shown
    assert configured_window.vanilla_group.isHidden() is False
    assert (
        t("database_builder.validation.missing_assets")
        in configured_window.validation_status_label.text()
    )
    assert "crate icon" in configured_window.vanilla_info.text()


def test_on_validation_complete_missing_subicons(configured_window: IconImportWindow) -> None:
    """Test _on_validation_complete when subicons are missing.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    result = PakValidationResult()
    result.is_valid = False
    result.has_crate_icon = True
    result.has_subicons = False
    result.subicons_count = 0

    configured_window._is_validating = True

    configured_window._on_validation_complete(result)

    # Use isHidden() since window isn't shown
    assert configured_window.vanilla_group.isHidden() is False
    assert "subicons" in configured_window.vanilla_info.text()


def test_on_validation_complete_missing_both(configured_window: IconImportWindow) -> None:
    """Test _on_validation_complete when both assets are missing.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    result = PakValidationResult()
    result.is_valid = False
    result.has_crate_icon = False
    result.has_subicons = False
    result.subicons_count = 0

    configured_window._is_validating = True

    configured_window._on_validation_complete(result)

    # Use isHidden() since window isn't shown
    assert configured_window.vanilla_group.isHidden() is False
    assert "crate icon" in configured_window.vanilla_info.text()
    assert "subicons" in configured_window.vanilla_info.text()


def test_set_pak_controls_enabled_disable(configured_window: IconImportWindow) -> None:
    """Test _set_pak_controls_enabled disables controls.

    Args:
        configured_window: Configured window instance
    """
    configured_window._set_pak_controls_enabled(False)

    assert configured_window.add_mod_pak_button.isEnabled() is False
    assert configured_window.remove_mod_pak_button.isEnabled() is False
    assert configured_window.clear_mod_pak_button.isEnabled() is False
    assert configured_window.mod_pak_list_widget.acceptDrops() is False


def test_set_pak_controls_enabled_enable(configured_window: IconImportWindow) -> None:
    """Test _set_pak_controls_enabled enables controls.

    Args:
        configured_window: Configured window instance
    """
    # First disable
    configured_window._set_pak_controls_enabled(False)

    # Then enable
    configured_window._set_pak_controls_enabled(True)

    assert configured_window.add_mod_pak_button.isEnabled() is True
    assert configured_window.remove_mod_pak_button.isEnabled() is True
    assert configured_window.clear_mod_pak_button.isEnabled() is True
    assert configured_window.mod_pak_list_widget.acceptDrops() is True


def test_validate_inputs_while_validating(configured_window: IconImportWindow) -> None:
    """Test validation fails when PAK validation is in progress.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window._is_validating = True

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.wait_validation")


def test_validate_inputs_vanilla_required_but_missing(
    configured_window: IconImportWindow,
) -> None:
    """Test validation fails when vanilla PAK is required but not selected.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")

    result = PakValidationResult()
    result.is_valid = False
    configured_window._validation_result = result
    configured_window.vanilla_pak_file = None

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.mod_missing_assets")


def test_validate_inputs_vanilla_required_and_provided(
    configured_window: IconImportWindow,
) -> None:
    """Test validation passes when vanilla PAK is required, provided, and validated.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window.db_path_input.setText("/tmp/test.h5")

    # Mod PAK validation shows missing assets
    mod_result = PakValidationResult()
    mod_result.is_valid = False
    configured_window._validation_result = mod_result

    # Vanilla PAK is provided and validated as valid
    configured_window.vanilla_pak_file = "vanilla.pak"
    vanilla_result = PakValidationResult()
    vanilla_result.is_valid = True
    configured_window._vanilla_validation_result = vanilla_result

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is True


def test_validate_inputs_vanilla_provided_but_invalid(
    configured_window: IconImportWindow,
) -> None:
    """Test validation fails when vanilla PAK is provided but invalid.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")

    # Mod PAK validation shows missing assets
    mod_result = PakValidationResult()
    mod_result.is_valid = False
    configured_window._validation_result = mod_result

    # Vanilla PAK is provided but validation shows it's also invalid
    configured_window.vanilla_pak_file = "wrong.pak"
    vanilla_result = PakValidationResult()
    vanilla_result.is_valid = False
    configured_window._vanilla_validation_result = vanilla_result

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.vanilla_invalid")


def test_validate_inputs_vanilla_provided_not_validated(
    configured_window: IconImportWindow,
) -> None:
    """Test validation fails when vanilla PAK is provided but not yet validated.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")

    # Mod PAK validation shows missing assets
    mod_result = PakValidationResult()
    mod_result.is_valid = False
    configured_window._validation_result = mod_result

    # Vanilla PAK is provided but not yet validated
    configured_window.vanilla_pak_file = "vanilla.pak"
    configured_window._vanilla_validation_result = None

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.wait_vanilla_validation")


def test_validate_inputs_while_validating_vanilla(
    configured_window: IconImportWindow,
) -> None:
    """Test validation fails when vanilla PAK validation is in progress.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_name_input.setText("test_mod")
    configured_window._is_validating_vanilla = True

    is_valid, error_msg = configured_window.validate_inputs()

    assert is_valid is False
    assert error_msg == t("database_builder.validation.wait_vanilla_validation")


def test_trigger_vanilla_validation_no_file(configured_window: IconImportWindow) -> None:
    """Test vanilla validation does nothing when no file selected.

    Args:
        configured_window: Configured window instance
    """
    configured_window.vanilla_pak_file = None

    # Should return early without doing anything
    configured_window._trigger_vanilla_validation()

    assert configured_window._is_validating_vanilla is False


def test_trigger_vanilla_validation_no_extractor(configured_window: IconImportWindow) -> None:
    """Test vanilla validation logs warning when extractor not configured.

    Args:
        configured_window: Configured window instance
    """
    configured_window.vanilla_pak_file = "test.pak"
    configured_window.settings.external_tools.repak = None

    # Should return early without starting validation
    configured_window._trigger_vanilla_validation()

    assert configured_window._is_validating_vanilla is False


def test_trigger_vanilla_validation_starts_worker(
    configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test vanilla validation starts worker when properly configured.

    Args:
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    extractor = tmp_path / "repak.exe"
    extractor.touch()
    configured_window.settings.external_tools.repak = extractor
    configured_window.vanilla_pak_file = str(tmp_path / "vanilla.pak")

    with patch("fs_tools.gui.windows.icon_import_window.PakValidationWorker") as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        configured_window._trigger_vanilla_validation()

        assert configured_window._is_validating_vanilla is True
        mock_worker.start.assert_called_once()


def test_on_vanilla_validation_complete_valid(configured_window: IconImportWindow) -> None:
    """Test handling valid vanilla PAK validation result.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    result = PakValidationResult()
    result.is_valid = True
    result.has_crate_icon = True
    result.has_subicons = True
    result.subicons_count = 25

    configured_window._is_validating_vanilla = True
    configured_window._on_vanilla_validation_complete(result)

    assert configured_window._is_validating_vanilla is False
    assert configured_window._vanilla_validation_result == result
    assert (
        t("database_builder.validation.all_assets_found")
        in configured_window.validation_status_label.text()
    )
    # Warning message should be hidden when valid
    assert configured_window.vanilla_info.isHidden() is True


def test_on_vanilla_validation_complete_invalid(
    configured_window: IconImportWindow,
) -> None:
    """Test handling invalid vanilla PAK validation result.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    result = PakValidationResult()
    result.is_valid = False
    result.has_crate_icon = False
    result.has_subicons = False

    configured_window._is_validating_vanilla = True

    with patch("fs_tools.gui.windows.icon_import_window.QMessageBox.warning") as mock_warning:
        configured_window._on_vanilla_validation_complete(result)

    assert configured_window._is_validating_vanilla is False
    assert configured_window._vanilla_validation_result == result
    assert (
        t("database_builder.validation.invalid_vanilla")
        in configured_window.validation_status_label.text()
    )
    # Warning message should be visible when invalid
    assert configured_window.vanilla_info.isHidden() is False
    mock_warning.assert_called_once()


def test_set_vanilla_controls_enabled(configured_window: IconImportWindow) -> None:
    """Test enabling and disabling vanilla PAK controls.

    Args:
        configured_window: Configured window instance
    """
    # Disable controls
    configured_window._set_vanilla_controls_enabled(False)
    assert configured_window.vanilla_browse_button.isEnabled() is False
    assert configured_window.vanilla_clear_button.isEnabled() is False

    # Enable controls
    configured_window._set_vanilla_controls_enabled(True)
    assert configured_window.vanilla_browse_button.isEnabled() is True
    assert configured_window.vanilla_clear_button.isEnabled() is True


def test_trigger_validation_cancels_existing(
    configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test that triggering validation waits for existing worker.

    Args:
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    extractor = tmp_path / "repak.exe"
    extractor.touch()
    configured_window.settings.external_tools.repak = extractor
    configured_window.mod_pak_files = ["test.pak"]

    # Create a mock worker that appears to be running
    mock_existing_worker = MagicMock()
    mock_existing_worker.isRunning.return_value = True
    configured_window.validation_worker = mock_existing_worker

    with patch("fs_tools.gui.windows.icon_import_window.PakValidationWorker") as mock_worker_class:
        mock_new_worker = MagicMock()
        mock_worker_class.return_value = mock_new_worker

        configured_window._trigger_validation()

        # Should have waited for existing worker
        mock_existing_worker.wait.assert_called_once()


def test_close_event_with_vanilla_validation_worker_running(
    configured_window: IconImportWindow,
) -> None:
    """Test close event waits for vanilla validation worker.

    Args:
        configured_window: Configured window instance
    """
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    configured_window.vanilla_validation_worker = mock_worker

    mock_event = MagicMock()

    with patch.object(configured_window, "_cleanup_and_accept"):
        configured_window.closeEvent(mock_event)

    mock_worker.wait.assert_called_once()


def test_log_key_press_event_none(configured_window: IconImportWindow) -> None:
    """Test log key press event handles None event.

    Args:
        configured_window: Configured window instance
    """
    # Should not raise
    configured_window._log_key_press_event(None)


def test_log_key_press_event_other_key(configured_window: IconImportWindow) -> None:
    """Test log key press event handles non-copy key.

    Args:
        configured_window: Configured window instance
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    # Create a key event for a non-copy key (e.g., Enter)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
    )

    # Should not raise and should call default handler
    with patch.object(QTableWidget, "keyPressEvent") as mock_default:
        configured_window._log_key_press_event(event)
        mock_default.assert_called_once()


def test_log_key_press_event_copy_key(configured_window: IconImportWindow) -> None:
    """Test log key press event handles copy key (Ctrl+C).

    Args:
        configured_window: Configured window instance
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    # Create a key event for Ctrl+C (Copy)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier,
    )

    # Should call _copy_selected_logs
    with patch.object(configured_window, "_copy_selected_logs") as mock_copy:
        configured_window._log_key_press_event(event)
        mock_copy.assert_called_once()


def test_copy_selected_logs_no_selection_model(configured_window: IconImportWindow) -> None:
    """Test copy logs handles missing selection model.

    Args:
        configured_window: Configured window instance
    """
    with patch.object(configured_window.log_display, "selectionModel", return_value=None):
        # Should not raise
        configured_window._copy_selected_logs()


def test_copy_selected_logs_no_selected_rows(configured_window: IconImportWindow) -> None:
    """Test copy logs handles empty selection.

    Args:
        configured_window: Configured window instance
    """
    mock_selection = MagicMock()
    mock_selection.selectedRows.return_value = []

    with patch.object(configured_window.log_display, "selectionModel", return_value=mock_selection):
        # Should not raise
        configured_window._copy_selected_logs()


def test_pak_drag_enter_event_while_validating(configured_window: IconImportWindow) -> None:
    """Test drag enter event is ignored while validating.

    Args:
        configured_window: Configured window instance
    """
    configured_window._is_validating = True

    mock_event = MagicMock(spec=QDragEnterEvent)
    configured_window.pak_drag_enter_event(mock_event)

    mock_event.ignore.assert_called_once()
    mock_event.accept.assert_not_called()


def test_pak_drop_event_while_validating(
    configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test drop event is ignored while validating.

    Args:
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    configured_window._is_validating = True
    test_pak = str(tmp_path / "test.pak")

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(test_pak)])

    mock_event = MagicMock(spec=QDropEvent)
    mock_event.mimeData.return_value = mime_data

    configured_window.pak_drop_event(mock_event)

    mock_event.ignore.assert_called_once()
    mock_event.accept.assert_not_called()
    assert test_pak not in configured_window.mod_pak_files


def test_clear_all_paks_clears_validation_state(
    qtbot: Any, configured_window: IconImportWindow, tmp_path: Path
) -> None:
    """Test clearing all PAKs also clears validation state.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
        tmp_path: Temporary directory path
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    # Set up some state
    configured_window.mod_pak_files = ["test.pak"]
    configured_window.mod_pak_list_widget.addItem("test.pak")
    configured_window._validation_result = PakValidationResult()
    configured_window.validation_status_label.setText("Some status")
    configured_window.vanilla_group.setVisible(True)
    configured_window.vanilla_pak_file = "vanilla.pak"

    configured_window.clear_all_mod_paks()

    assert configured_window.mod_pak_files == []
    assert configured_window._validation_result is None
    assert configured_window.validation_status_label.text() == ""
    # Use isHidden() since window isn't shown
    assert configured_window.vanilla_group.isHidden() is True
    assert configured_window.vanilla_pak_file is None


def test_close_event_with_validation_worker_running(
    qtbot: Any, configured_window: IconImportWindow
) -> None:
    """Test close event waits for validation worker.

    Args:
        qtbot: PyQt test fixture
        configured_window: Configured window instance
    """
    mock_validation_worker = MagicMock()
    mock_validation_worker.isRunning.return_value = True
    configured_window.validation_worker = mock_validation_worker

    mock_event = MagicMock()

    configured_window.closeEvent(mock_event)

    mock_validation_worker.wait.assert_called_once()
    mock_event.accept.assert_called_once()


def test_update_start_button_state_validating(configured_window: IconImportWindow) -> None:
    """Test start button disabled while validating mod PAK.

    Args:
        configured_window: Configured window instance
    """
    configured_window._is_validating = True
    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is False


def test_update_start_button_state_validating_vanilla(
    configured_window: IconImportWindow,
) -> None:
    """Test start button disabled while validating vanilla PAK.

    Args:
        configured_window: Configured window instance
    """
    configured_window._is_validating_vanilla = True
    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is False


def test_update_start_button_state_no_mod_files(
    configured_window: IconImportWindow,
) -> None:
    """Test start button enabled when no mod PAK files selected.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = []
    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is True


def test_update_start_button_state_mod_validation_passed(
    configured_window: IconImportWindow,
) -> None:
    """Test start button enabled when mod PAK validation passed.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]
    result = PakValidationResult()
    result.is_valid = True
    configured_window._validation_result = result

    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is True


def test_update_start_button_state_mod_validation_failed_no_vanilla(
    configured_window: IconImportWindow,
) -> None:
    """Test start button disabled when mod PAK validation failed and no vanilla PAK.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]
    result = PakValidationResult()
    result.is_valid = False
    configured_window._validation_result = result
    configured_window._vanilla_validation_result = None

    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is False


def test_update_start_button_state_mod_validation_failed_vanilla_valid(
    configured_window: IconImportWindow,
) -> None:
    """Test start button enabled when mod failed but vanilla is valid.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]

    mod_result = PakValidationResult()
    mod_result.is_valid = False
    configured_window._validation_result = mod_result

    vanilla_result = PakValidationResult()
    vanilla_result.is_valid = True
    configured_window._vanilla_validation_result = vanilla_result

    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is True


def test_update_start_button_state_mod_validation_failed_vanilla_invalid(
    configured_window: IconImportWindow,
) -> None:
    """Test start button disabled when both mod and vanilla validation failed.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    configured_window.mod_pak_files = ["test.pak"]

    mod_result = PakValidationResult()
    mod_result.is_valid = False
    configured_window._validation_result = mod_result

    vanilla_result = PakValidationResult()
    vanilla_result.is_valid = False
    configured_window._vanilla_validation_result = vanilla_result

    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is False


def test_update_start_button_state_no_validation_result(
    configured_window: IconImportWindow,
) -> None:
    """Test start button enabled when no validation has been run yet.

    Args:
        configured_window: Configured window instance
    """
    configured_window.mod_pak_files = ["test.pak"]
    configured_window._validation_result = None

    configured_window._update_start_button_state()
    assert configured_window.start_button.isEnabled() is True


def test_clear_vanilla_pak_restores_warning_state(
    configured_window: IconImportWindow,
) -> None:
    """Test clearing vanilla PAK restores warning state when mod validation failed.

    Args:
        configured_window: Configured window instance
    """
    from foxhole_stockpiles.models.pak_validation_result import PakValidationResult

    # Set up mod PAK files (required for start button state logic)
    configured_window.mod_pak_files = ["test.pak"]

    # Set up invalid mod validation result
    mod_result = PakValidationResult()
    mod_result.is_valid = False
    configured_window._validation_result = mod_result

    # Set up valid vanilla PAK
    configured_window.vanilla_pak_file = "vanilla.pak"
    vanilla_result = PakValidationResult()
    vanilla_result.is_valid = True
    configured_window._vanilla_validation_result = vanilla_result
    configured_window.vanilla_info.setVisible(False)
    configured_window.validation_status_label.setText("All required assets found")

    # Clear the vanilla PAK
    configured_window.clear_vanilla_pak()

    # Should restore warning state
    assert configured_window.vanilla_pak_file is None
    assert configured_window._vanilla_validation_result is None
    # Use isHidden() since window isn't shown
    assert configured_window.vanilla_info.isHidden() is False
    assert (
        t("database_builder.validation.missing_assets")
        in configured_window.validation_status_label.text()
    )
    # Start button should be disabled since mod validation failed and no vanilla
    assert configured_window.start_button.isEnabled() is False
