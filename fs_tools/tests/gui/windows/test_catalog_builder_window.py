"""Tests for CatalogBuilderWindow."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.i18n import t
from fs_tools.gui.windows.catalog_builder_window import CatalogBuilderWindow


# Prevent any GUI dialogs from appearing during test cleanup
@pytest.fixture(autouse=True)
def prevent_dialog_on_close() -> Generator[None, None, None]:
    """Prevent dialogs during window cleanup."""
    with patch(
        "fs_tools.gui.windows.catalog_builder_window.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        yield


@pytest.fixture
def configured_settings() -> AppSettings:
    """Create default settings for testing.

    Returns:
        AppSettings: Default settings (the catalog builder needs no external tools)
    """
    return AppSettings()


@pytest.fixture
def configured_window(
    qtbot: Any, configured_settings: AppSettings
) -> Generator[CatalogBuilderWindow, None, None]:
    """Create a configured CatalogBuilderWindow.

    Args:
        qtbot: PyQt test fixture
        configured_settings: Configured settings

    Yields:
        CatalogBuilderWindow: Window instance
    """
    with patch("fs_tools.gui.windows.catalog_builder_window.get_settings") as mock_get_settings:
        mock_get_settings.return_value = configured_settings
        window = CatalogBuilderWindow()
        qtbot.addWidget(window)
        yield window
        # Cleanup: stop any running workers
        if window.build_worker and window.build_worker.isRunning():
            window.build_worker.stop()
            window.build_worker.wait()


# ===== Initialization Tests =====


def test_configured_window_initialization(configured_window: CatalogBuilderWindow) -> None:
    """Test configured window initialization."""
    assert configured_window.windowTitle() == t("catalog_builder.title")
    assert CatalogBuilderWindow.requirements_met(configured_window.settings) is True
    assert configured_window.pak_file is None
    assert configured_window.build_worker is None


# ===== Check Configuration Tests =====


def test_requirements_met_needs_no_external_tools() -> None:
    """The catalog builder is always available: it reads the PAK directly."""
    assert CatalogBuilderWindow.requirements_met(AppSettings()) is True


# ===== PAK File Selection Tests =====


def test_select_pak_file(qtbot: Any, configured_window: CatalogBuilderWindow) -> None:
    """Test selecting PAK file via dialog."""
    test_path = "/path/to/test.pak"

    with patch(
        "fs_tools.gui.windows.catalog_builder_window.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "PAK Files (*.pak)")
        configured_window.select_pak_file()
        assert configured_window.pak_file == test_path


def test_select_pak_file_cancelled(configured_window: CatalogBuilderWindow) -> None:
    """Test selecting PAK file when cancelled."""
    with patch(
        "fs_tools.gui.windows.catalog_builder_window.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")
        configured_window.select_pak_file()
        assert configured_window.pak_file is None


# ===== Output Path Selection Tests =====


def test_select_output_path(configured_window: CatalogBuilderWindow) -> None:
    """Test selecting output path via dialog."""
    test_path = "/path/to/catalog.json"

    with patch(
        "fs_tools.gui.windows.catalog_builder_window.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "JSON Files (*.json)")
        configured_window.select_output_path()
        assert configured_window.output_path_input.text() == test_path


def test_select_output_path_adds_extension(configured_window: CatalogBuilderWindow) -> None:
    """Test selecting output path adds .json extension if missing."""
    with patch(
        "fs_tools.gui.windows.catalog_builder_window.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("/path/to/catalog", "JSON Files (*.json)")
        configured_window.select_output_path()
        assert configured_window.output_path_input.text() == "/path/to/catalog.json"


# ===== Validate Inputs Tests =====


def test_validate_inputs_no_pak_file(configured_window: CatalogBuilderWindow) -> None:
    """Test validate_inputs fails when no PAK file selected."""
    configured_window.pak_file = None
    configured_window.output_path_input.setText("catalog.json")
    is_valid, error_msg = configured_window.validate_inputs()
    assert is_valid is False
    assert error_msg == t("catalog_builder.validation.select_pak")


def test_validate_inputs_success(configured_window: CatalogBuilderWindow, tmp_path: Path) -> None:
    """Test validate_inputs succeeds with valid inputs."""
    pak_file = tmp_path / "test.pak"
    pak_file.touch()
    configured_window.pak_file = str(pak_file)
    configured_window.output_path_input.setText("catalog.json")
    is_valid, error_msg = configured_window.validate_inputs()
    assert is_valid is True


# ===== Build Process Tests =====


def test_start_build_validation_failure(configured_window: CatalogBuilderWindow) -> None:
    """Test start_build shows warning when validation fails."""
    configured_window.pak_file = None

    with patch("fs_tools.gui.windows.catalog_builder_window.QMessageBox.warning") as mock_warning:
        configured_window.start_build()
        mock_warning.assert_called_once()


def test_start_build_creates_worker(
    configured_window: CatalogBuilderWindow, tmp_path: Path
) -> None:
    """Test start_build creates and starts worker."""
    pak_file = tmp_path / "test.pak"
    pak_file.touch()
    configured_window.pak_file = str(pak_file)
    configured_window.output_path_input.setText(str(tmp_path / "catalog.json"))

    with patch(
        "fs_tools.gui.windows.catalog_builder_window.CatalogBuilderWorker"
    ) as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker
        configured_window.start_build()
        mock_worker_class.assert_called_once()
        mock_worker.start.assert_called_once()
        assert configured_window.start_button.isEnabled() is False


def test_full_catalog_is_off_by_default(configured_window: CatalogBuilderWindow) -> None:
    """The default catalog drops audio, visual and engine-internal fields."""
    assert configured_window.full_checkbox.isChecked() is False


def test_start_build_passes_pak_output_and_full_flag(
    configured_window: CatalogBuilderWindow, tmp_path: Path
) -> None:
    """start_build hands the PAK, the output path and the full flag to the worker."""
    pak_file = tmp_path / "test.pak"
    pak_file.touch()
    output = tmp_path / "catalog.json"
    configured_window.pak_file = str(pak_file)
    configured_window.output_path_input.setText(str(output))
    configured_window.full_checkbox.setChecked(True)

    with patch(
        "fs_tools.gui.windows.catalog_builder_window.CatalogBuilderWorker"
    ) as mock_worker_class:
        mock_worker_class.return_value = MagicMock()
        configured_window.start_build()
        mock_worker_class.assert_called_once_with(pak_file=pak_file, output_path=output, full=True)
        assert configured_window.full_checkbox.isEnabled() is False


def test_on_build_finished_reenables_the_full_checkbox(
    configured_window: CatalogBuilderWindow,
) -> None:
    """Finishing a build re-enables the full catalog option."""
    configured_window.full_checkbox.setEnabled(False)
    configured_window.on_build_finished(False)
    assert configured_window.full_checkbox.isEnabled() is True


def test_cancel_build(configured_window: CatalogBuilderWindow) -> None:
    """Test cancel_build stops worker."""
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    configured_window.build_worker = mock_worker
    configured_window.cancel_build()
    mock_worker.stop.assert_called_once()


def test_on_build_finished_success(configured_window: CatalogBuilderWindow) -> None:
    """Test on_build_finished re-enables controls on success."""
    configured_window.start_button.setEnabled(False)
    configured_window.on_build_finished(True)
    assert configured_window.start_button.isEnabled() is True


def test_on_build_error(configured_window: CatalogBuilderWindow) -> None:
    """Test on_build_error adds error to log."""
    initial_rows = configured_window.log_display.rowCount()
    configured_window.on_build_error("Test error message")
    assert configured_window.log_display.rowCount() == initial_rows + 1


def test_on_build_progress(configured_window: CatalogBuilderWindow) -> None:
    """Test on_build_progress adds progress to log."""
    initial_rows = configured_window.log_display.rowCount()
    configured_window.on_build_progress("Processing files...")
    assert configured_window.log_display.rowCount() == initial_rows + 1


# ===== Log Display Tests =====


def test_clear_logs(configured_window: CatalogBuilderWindow) -> None:
    """Test clear_logs clears the log display."""
    configured_window.on_build_progress("Test")
    assert configured_window.log_display.rowCount() > 0
    configured_window.clear_logs()
    assert configured_window.log_display.rowCount() == 0


def test_append_log(configured_window: CatalogBuilderWindow) -> None:
    """Test append_log adds log entry."""
    log_data = {
        "timestamp": "2024-01-01 12:00:00",
        "level": "INFO",
        "module": "test",
        "message": "Test message",
        "color": "#FFFFFF",
    }
    initial_rows = configured_window.log_display.rowCount()
    configured_window.append_log(log_data)
    assert configured_window.log_display.rowCount() == initial_rows + 1


# ===== Key Press Event Tests =====


def test_log_key_press_event_none(configured_window: CatalogBuilderWindow) -> None:
    """Test _log_key_press_event handles None event."""
    configured_window._log_key_press_event(None)  # Should not raise


def test_log_key_press_event_copy(configured_window: CatalogBuilderWindow) -> None:
    """Test _log_key_press_event handles copy key."""
    with patch.object(configured_window, "_copy_selected_logs") as mock_copy:
        event = MagicMock()
        event.matches = MagicMock(return_value=True)
        configured_window._log_key_press_event(event)
        mock_copy.assert_called_once()


def test_log_key_press_event_other(configured_window: CatalogBuilderWindow) -> None:
    """Test _log_key_press_event handles other keys."""
    with patch(
        "fs_tools.gui.windows.catalog_builder_window.QTableWidget.keyPressEvent"
    ) as mock_key_press:
        event = MagicMock()
        event.matches = MagicMock(return_value=False)
        configured_window._log_key_press_event(event)
        mock_key_press.assert_called_once()


# ===== Copy Logs Tests =====


def test_copy_selected_logs_no_selection(configured_window: CatalogBuilderWindow) -> None:
    """Test _copy_selected_logs handles no selection."""
    configured_window._copy_selected_logs()  # Should not raise


def test_copy_selected_logs_with_selection(configured_window: CatalogBuilderWindow) -> None:
    """Test _copy_selected_logs copies selected rows."""
    log_data = {
        "timestamp": "2024-01-01 12:00:00",
        "level": "INFO",
        "module": "test",
        "message": "Test message",
        "color": "#FFFFFF",
    }
    configured_window.append_log(log_data)
    configured_window.log_display.selectRow(0)

    with patch.object(QApplication, "clipboard") as mock_clipboard:
        mock_cb = MagicMock()
        mock_clipboard.return_value = mock_cb
        configured_window._copy_selected_logs()
        mock_cb.setText.assert_called_once()


# ===== Close Event Tests =====


def test_close_event_no_worker(configured_window: CatalogBuilderWindow) -> None:
    """Test close event when no worker running."""
    configured_window.build_worker = None
    mock_event = MagicMock()
    configured_window.closeEvent(mock_event)
    mock_event.accept.assert_called_once()


def test_close_event_worker_running_confirm(configured_window: CatalogBuilderWindow) -> None:
    """Test close event when worker running and user confirms."""
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    configured_window.build_worker = mock_worker
    mock_event = MagicMock()

    with patch("fs_tools.gui.windows.catalog_builder_window.QMessageBox.question") as mock_question:
        mock_question.return_value = QMessageBox.StandardButton.Yes
        configured_window.closeEvent(mock_event)
        mock_worker.stop.assert_called_once()
        mock_event.accept.assert_called_once()


def test_close_event_worker_running_cancel(configured_window: CatalogBuilderWindow) -> None:
    """Test close event when worker running and user cancels."""
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    configured_window.build_worker = mock_worker
    mock_event = MagicMock()

    with patch("fs_tools.gui.windows.catalog_builder_window.QMessageBox.question") as mock_question:
        mock_question.return_value = QMessageBox.StandardButton.No
        configured_window.closeEvent(mock_event)
        mock_event.ignore.assert_called_once()


# ===== Default PAK Directory Tests =====


def test_get_default_pak_directory(configured_window: CatalogBuilderWindow) -> None:
    """Test _get_default_pak_directory returns a path."""
    with patch("platform.system", return_value="Unknown"):
        result = configured_window._get_default_pak_directory()
        assert result is not None


def test_get_default_pak_directory_linux_not_wsl(
    configured_window: CatalogBuilderWindow,
) -> None:
    """Test _get_default_pak_directory on Linux (not WSL)."""
    with patch("platform.system", return_value="Linux"):
        with patch("builtins.open", side_effect=OSError):
            result = configured_window._get_default_pak_directory()
            assert result is not None
