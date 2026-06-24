"""Tests for CatalogBuilderWindow."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.sections.external_tools import ExternalToolsSettings
from foxhole_stockpiles.i18n import t
from fs_tools.gui.windows.catalog_builder_window import CatalogBuilderWindow
from fs_tools.services.catalog_builder import (
    CatalogPreset,
    CatalogRule,
    CatalogRuleSet,
    RuleAction,
    preset_ruleset,
)


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
def configured_settings(tmp_path: Path) -> AppSettings:
    """Create configured settings for testing.

    Args:
        tmp_path: Temporary directory path

    Returns:
        AppSettings: Configured settings
    """
    repak_path = tmp_path / "repak.exe"
    repak_path.touch()
    uassetgui_path = tmp_path / "uassetgui.exe"
    uassetgui_path.touch()

    return AppSettings(
        external_tools=ExternalToolsSettings(
            repak=repak_path,
            uassetgui=uassetgui_path,
        )
    )


@pytest.fixture
def unconfigured_settings() -> AppSettings:
    """Create unconfigured settings for testing.

    Returns:
        AppSettings: Unconfigured settings (missing tools)
    """
    return AppSettings(
        external_tools=ExternalToolsSettings(
            repak=None,
            uassetgui=None,
        )
    )


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


@pytest.fixture
def unconfigured_window(
    qtbot: Any, unconfigured_settings: AppSettings
) -> Generator[CatalogBuilderWindow, None, None]:
    """Create an unconfigured CatalogBuilderWindow.

    Args:
        qtbot: PyQt test fixture
        unconfigured_settings: Unconfigured settings

    Yields:
        CatalogBuilderWindow: Window instance
    """
    with patch("fs_tools.gui.windows.catalog_builder_window.get_settings") as mock_get_settings:
        mock_get_settings.return_value = unconfigured_settings
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


def test_unconfigured_window_shows_warning(unconfigured_window: CatalogBuilderWindow) -> None:
    """Test unconfigured window shows configuration warning."""
    assert CatalogBuilderWindow.requirements_met(unconfigured_window.settings) is False


# ===== Check Configuration Tests =====


def test_requirements_met_true(configured_window: CatalogBuilderWindow) -> None:
    """Test requirements_met returns True when configured."""
    assert CatalogBuilderWindow.requirements_met(configured_window.settings) is True


def test_requirements_met_missing_tools(qtbot: Any, tmp_path: Path) -> None:
    """Test requirements_met returns False when tools missing."""
    settings = AppSettings(external_tools=ExternalToolsSettings(repak=None, uassetgui=None))

    with patch("fs_tools.gui.windows.catalog_builder_window.get_settings") as mock_get_settings:
        mock_get_settings.return_value = settings
        window = CatalogBuilderWindow()
        qtbot.addWidget(window)
        assert CatalogBuilderWindow.requirements_met(window.settings) is False


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


def test_preset_combo_defaults_to_full(configured_window: CatalogBuilderWindow) -> None:
    """The preset dropdown defaults to the FULL catalog (backwards compatible)."""
    assert configured_window.variant_combo.currentData() == CatalogPreset.FULL
    assert configured_window.ruleset == preset_ruleset(CatalogPreset.FULL)


def test_selecting_fs_preset_updates_ruleset(configured_window: CatalogBuilderWindow) -> None:
    """Selecting the FS preset seeds the window's rule set."""
    fs_index = configured_window.variant_combo.findData(CatalogPreset.FS)
    configured_window.variant_combo.setCurrentIndex(fs_index)
    assert configured_window.ruleset == preset_ruleset(CatalogPreset.FS)


def test_start_build_passes_ruleset(
    configured_window: CatalogBuilderWindow, tmp_path: Path
) -> None:
    """start_build builds the worker with the window's current rule set."""
    pak_file = tmp_path / "test.pak"
    pak_file.touch()
    configured_window.pak_file = str(pak_file)
    configured_window.output_path_input.setText(str(tmp_path / "catalog.json"))
    configured_window.ruleset = preset_ruleset(CatalogPreset.FS)

    with patch(
        "fs_tools.gui.windows.catalog_builder_window.CatalogBuilderWorker"
    ) as mock_worker_class:
        mock_worker_class.return_value = MagicMock()
        configured_window.start_build()
        _, kwargs = mock_worker_class.call_args
        assert kwargs["ruleset"] == preset_ruleset(CatalogPreset.FS)


def test_start_build_warns_when_required_missing(
    configured_window: CatalogBuilderWindow, tmp_path: Path
) -> None:
    """A rule set missing required fields warns and aborts when declined."""
    pak_file = tmp_path / "test.pak"
    pak_file.touch()
    configured_window.pak_file = str(pak_file)
    configured_window.output_path_input.setText(str(tmp_path / "catalog.json"))
    # Drops everything -> required minimum missing.
    configured_window.ruleset = CatalogRuleSet(
        rules=[CatalogRule(action=RuleAction.EXCLUDE, pattern="**")]
    )

    with (
        patch(
            "fs_tools.gui.windows.catalog_builder_window.QMessageBox.warning",
            return_value=QMessageBox.StandardButton.No,
        ) as mock_warning,
        patch(
            "fs_tools.gui.windows.catalog_builder_window.CatalogBuilderWorker"
        ) as mock_worker_class,
    ):
        configured_window.start_build()
        mock_warning.assert_called_once()
        mock_worker_class.assert_not_called()


def test_edit_rules_adopts_dialog_ruleset(configured_window: CatalogBuilderWindow) -> None:
    """Accepting the rules dialog adopts its rule set."""
    fs = preset_ruleset(CatalogPreset.FS)
    with patch("fs_tools.gui.windows.catalog_builder_window.RulesDialog") as mock_dialog_class:
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1  # QDialog.DialogCode.Accepted
        mock_dialog.ruleset = fs
        mock_dialog_class.return_value = mock_dialog
        configured_window._edit_rules()
        assert configured_window.ruleset == fs
        assert configured_window.variant_combo.currentData() == CatalogPreset.FS


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
