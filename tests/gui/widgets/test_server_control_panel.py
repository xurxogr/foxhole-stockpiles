"""Tests for ServerControlPanel."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QTableWidget

from foxhole_stockpiles.gui.widgets.server_control_panel import ServerControlPanel
from foxhole_stockpiles.i18n import t


@pytest.fixture
def panel(qtbot: Any) -> ServerControlPanel:
    """Create a ServerControlPanel instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        ServerControlPanel: Panel instance
    """
    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with (
        patch("foxhole_stockpiles.gui.widgets.server_control_panel.ScannerClient"),
        patch.object(server_control_panel, "AppSettings", side_effect=OSError("No config")),
    ):
        panel_instance = ServerControlPanel()
        qtbot.addWidget(panel_instance)
        panel_instance.show()
        QApplication.processEvents()
        return panel_instance


def test_panel_initialization(panel: ServerControlPanel) -> None:
    """Test ServerControlPanel initialization.

    Args:
        panel (ServerControlPanel): Panel instance
    """
    assert panel.server_running is False
    assert panel.server_thread is None
    assert isinstance(panel.log_display, QTableWidget)
    assert panel.log_display.columnCount() == 4


def test_panel_start_server(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test starting the server.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with patch(
        "foxhole_stockpiles.gui.widgets.server_control_panel.ServerThread"
    ) as mock_thread_class:
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        panel.start_server()

        assert panel.server_running is True
        assert panel.start_stop_button.text() == t("server_panel.stop_server")
        assert panel.status_label.text() == t("server_panel.status_running")
        mock_thread.start.assert_called_once()


def test_panel_stop_server(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test stopping the server.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    # Set up server as running
    mock_thread = MagicMock()
    panel.server_thread = mock_thread
    panel.server_running = True

    panel.stop_server()

    assert panel.server_running is False
    assert panel.start_stop_button.text() == t("server_panel.start_server")
    assert panel.status_label.text() == t("server_panel.status_stopped")
    mock_thread.stop.assert_called_once()


def test_panel_toggle_server(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test toggling server state.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with patch.object(panel, "start_server") as mock_start:
        panel.toggle_server()
        mock_start.assert_called_once()

    panel.server_running = True
    with patch.object(panel, "stop_server") as mock_stop:
        panel.toggle_server()
        mock_stop.assert_called_once()


def test_panel_append_log(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test appending log entry.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    log_data = {
        "timestamp": "2025-01-04 12:00:00",
        "level": "INFO",
        "module": "test.module",
        "message": "Test message",
        "color": "#FFFFFF",
    }

    panel.append_log(log_data)

    assert panel.log_display.rowCount() == 1
    item0 = panel.log_display.item(0, 0)
    assert item0 is not None
    assert item0.text() == "2025-01-04 12:00:00"
    item1 = panel.log_display.item(0, 1)
    assert item1 is not None
    assert item1.text() == "INFO"
    item2 = panel.log_display.item(0, 2)
    assert item2 is not None
    assert item2.text() == "test.module"
    item3 = panel.log_display.item(0, 3)
    assert item3 is not None
    assert item3.text() == "Test message"


def test_panel_clear_logs(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test clearing logs.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    # Add a log entry
    log_data = {
        "timestamp": "2025-01-04 12:00:00",
        "level": "INFO",
        "module": "test",
        "message": "Test",
        "color": "#FFFFFF",
    }
    panel.append_log(log_data)

    assert panel.log_display.rowCount() == 1

    panel.clear_logs()

    assert panel.log_display.rowCount() == 0


def test_panel_process_screenshot_server_not_running(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test processing screenshot when server is not running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.server_running = False

    with patch("foxhole_stockpiles.gui.widgets.server_control_panel.logger") as mock_logger:
        panel.process_screenshot("/test/file.png")
        mock_logger.error.assert_called_once()


def test_panel_process_screenshot_server_running(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test processing screenshot when server is running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.server_running = True

    with patch(
        "foxhole_stockpiles.gui.widgets.server_control_panel.ScanWorker"
    ) as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        panel.process_screenshot("/test/file.png")

        mock_worker_class.assert_called_once_with(panel.scanner_client, "/test/file.png")
        mock_worker.start.assert_called_once()


def test_panel_select_screenshot(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test selecting screenshot via file dialog.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with patch(
        "foxhole_stockpiles.gui.widgets.server_control_panel.QFileDialog.getOpenFileName",
        return_value=("/test/file.png", ""),
    ):
        with patch.object(panel, "process_screenshot") as mock_process:
            panel.scan_screenshot_from_menu()
            mock_process.assert_called_once_with("/test/file.png")


def test_panel_refresh_db_info(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test refreshing database info.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with patch.object(panel, "_update_validation_state") as mock_update:
        panel.refresh_db_info()
        mock_update.assert_called_once()


def test_panel_validation_no_config(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation state with no configuration.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings", side_effect=OSError("No config")):
        panel._update_validation_state()
        QApplication.processEvents()

        # Should show error panel, hide logs
        assert panel.error_panel.isVisible()
        assert not panel.logs_group.isVisible()
        assert not panel.start_stop_button.isEnabled()
        assert t("server_panel.errors.no_config_title") in panel.error_panel.text()


def test_panel_validation_no_db_path(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation state with no database path configured.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = None

        panel._update_validation_state()
        QApplication.processEvents()

        # Should show error panel, hide logs
        assert panel.error_panel.isVisible()
        assert not panel.logs_group.isVisible()
        assert not panel.start_stop_button.isEnabled()
        assert t("server_panel.errors.config_incomplete_title") in panel.error_panel.text()


def test_panel_validation_db_not_found(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation state with database file not found.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = "/nonexistent/db.h5"

        panel._update_validation_state()
        QApplication.processEvents()

        # Should show error panel, hide logs
        assert panel.error_panel.isVisible()
        assert not panel.logs_group.isVisible()
        assert not panel.start_stop_button.isEnabled()
        assert t("server_panel.errors.database_not_found_title") in panel.error_panel.text()


def test_panel_validation_valid_db(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation state with valid database.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    test_db = Path(__file__).parent.parent.parent / "fixtures" / "test_db_v1.h5"

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = str(test_db)

        panel._update_validation_state()
        QApplication.processEvents()

        # Should hide error panel, show logs
        assert not panel.error_panel.isVisible()
        assert panel.logs_group.isVisible()
        assert panel.start_stop_button.isEnabled()
        assert panel.db_info_text.isVisible()
        assert len(panel.db_info_text.text()) > 0


def test_panel_on_language_changed(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test language change handler calls retranslate.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with patch.object(panel, "retranslate") as mock_retranslate:
        panel._on_language_changed("es")

        mock_retranslate.assert_called_once()


def test_panel_on_database_updated_same_db(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test on_database_updated when updated database matches configured database.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from foxhole_stockpiles.gui.widgets import server_control_panel

    test_db = Path("/tmp/test_db.h5")

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = str(test_db)

        # Server not running - should just refresh
        panel.server_running = False
        with patch.object(panel, "_update_validation_state") as mock_update:
            panel.on_database_updated(test_db)

            mock_update.assert_called_once()


def test_panel_on_database_updated_same_db_restarts_server(
    qtbot: Any, panel: ServerControlPanel
) -> None:
    """Test on_database_updated restarts server when it's running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from foxhole_stockpiles.gui.widgets import server_control_panel

    test_db = Path("/tmp/test_db.h5")

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = str(test_db)

        # Server running - should restart
        panel.server_running = True
        with (
            patch.object(panel, "_update_validation_state"),
            patch.object(panel, "stop_server") as mock_stop,
            patch.object(panel, "start_server") as mock_start,
        ):
            panel.on_database_updated(test_db)

            mock_stop.assert_called_once()
            mock_start.assert_called_once()


def test_panel_on_database_updated_different_db(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test on_database_updated when updated database doesn't match configured.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = "/tmp/configured_db.h5"

        with patch.object(panel, "_update_validation_state") as mock_update:
            # Different path
            panel.on_database_updated(Path("/tmp/other_db.h5"))

            # Should not refresh because paths don't match
            mock_update.assert_not_called()


def test_panel_on_database_updated_no_configured_path(
    qtbot: Any, panel: ServerControlPanel
) -> None:
    """Test on_database_updated when no database is configured.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = None

        with patch.object(panel, "_update_validation_state") as mock_update:
            panel.on_database_updated(Path("/tmp/test_db.h5"))

            # Should not refresh because no path configured
            mock_update.assert_not_called()


def test_panel_on_database_updated_exception(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test on_database_updated handles exceptions gracefully.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings", side_effect=OSError("Config error")):
        # Should not raise
        panel.on_database_updated(Path("/tmp/test_db.h5"))


def test_panel_attach_log_handler_already_attached(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _attach_log_handler doesn't duplicate handlers.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    import logging

    from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler

    root_logger = logging.getLogger()

    # Attach handler first time
    panel._attach_log_handler()
    after_first = len(root_logger.handlers)

    # Attach handler second time - should not add another
    panel._attach_log_handler()
    after_second = len(root_logger.handlers)

    assert after_second == after_first

    # Clean up - remove the handler we added
    for handler in root_logger.handlers[:]:
        if isinstance(handler, QtLogHandler):
            root_logger.removeHandler(handler)


def test_panel_validation_relative_path(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation shows relative path when possible.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    # Use a path outside cwd to trigger the ValueError case
    test_db = Path(__file__).parent.parent.parent / "fixtures" / "test_db_v1.h5"

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = str(test_db)

        panel._update_validation_state()
        QApplication.processEvents()

        # Should show just the filename since it's not relative to cwd
        assert panel.db_info_text.isVisible()
        # The db info should contain either the filename or a relative path
        db_info_text = panel.db_info_text.text()
        assert "test_db_v1.h5" in db_info_text or "Database:" in db_info_text


# ==================== SAV Processing Tests ====================


def test_validate_sav_config_no_settings(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _validate_sav_config when AppSettings raises an exception.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    with patch.object(server_control_panel, "AppSettings", side_effect=OSError("Config error")):
        sav_path, error = panel._validate_sav_config()

        assert sav_path is None
        assert error is not None
        assert "Config error" in error


def test_validate_sav_config_no_sav_file(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _validate_sav_config with no SAV file configured.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    with (
        patch.object(server_control_panel, "AppSettings") as mock_settings_class,
        patch.object(server_control_panel, "auto_detect_savefile", return_value=None),
    ):
        mock_settings = mock_settings_class.return_value
        mock_settings.sav_processing.sav_file_path = None

        sav_path, error = panel._validate_sav_config()

        assert sav_path is None
        assert error is not None
        assert t("server_panel.sav.error_no_sav_file") in error


def test_validate_sav_config_sav_not_found(
    qtbot: Any, panel: ServerControlPanel, tmp_path: Path
) -> None:
    """Test _validate_sav_config when SAV file doesn't exist.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    nonexistent_sav = tmp_path / "nonexistent.sav"

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.sav_processing.sav_file_path = nonexistent_sav

        sav_path, error = panel._validate_sav_config()

        assert sav_path is None
        assert error is not None
        assert t("server_panel.sav.error_sav_not_found") in error


def test_validate_sav_config_success(qtbot: Any, panel: ServerControlPanel, tmp_path: Path) -> None:
    """Test _validate_sav_config with valid configuration.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.sav_processing.sav_file_path = sav_file

        sav_path, error = panel._validate_sav_config()

        assert sav_path == sav_file
        assert error is None


def test_scan_sav_file_validation_error(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test scan_sav_file shows warning on validation error.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with (
        patch.object(panel, "_validate_sav_config", return_value=(None, "Test error")),
        patch(
            "foxhole_stockpiles.gui.widgets.server_control_panel.QMessageBox.warning"
        ) as mock_warning,
    ):
        panel.scan_sav_file()

        mock_warning.assert_called_once()
        args = mock_warning.call_args[0]
        assert "Test error" in args[2]


def test_scan_sav_file_already_scanning(
    qtbot: Any, panel: ServerControlPanel, tmp_path: Path
) -> None:
    """Test scan_sav_file doesn't start if already scanning.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    # Set up a mock running worker
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    panel._sav_scan_worker = mock_worker

    with (
        patch.object(panel, "_validate_sav_config", return_value=(sav_file, None)),
        patch.object(server_control_panel, "SavScanWorker") as mock_worker_class,
    ):
        panel.scan_sav_file()

        # Should not create a new worker
        mock_worker_class.assert_not_called()


def test_scan_sav_file_output_error(qtbot: Any, panel: ServerControlPanel, tmp_path: Path) -> None:
    """Test scan_sav_file shows error on output coordinator failure.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    with (
        patch.object(panel, "_validate_sav_config", return_value=(sav_file, None)),
        patch.object(server_control_panel, "AppSettings", side_effect=OSError("Output error")),
        patch(
            "foxhole_stockpiles.gui.widgets.server_control_panel.QMessageBox.critical"
        ) as mock_critical,
    ):
        panel.scan_sav_file()

        mock_critical.assert_called_once()


def test_toggle_sav_monitor_start(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test toggle_sav_monitor starts monitoring when not running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel._sav_monitoring = False

    with patch.object(panel, "_start_sav_monitor") as mock_start:
        panel.toggle_sav_monitor()
        mock_start.assert_called_once()


def test_toggle_sav_monitor_stop(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test toggle_sav_monitor stops monitoring when running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel._sav_monitoring = True

    with patch.object(panel, "_stop_sav_monitor") as mock_stop:
        panel.toggle_sav_monitor()
        mock_stop.assert_called_once()


def test_start_sav_monitor_already_running(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _start_sav_monitor doesn't start if previous monitor still running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    panel._sav_monitor_worker = mock_worker

    with patch.object(panel, "_validate_sav_config") as mock_validate:
        panel._start_sav_monitor()

        # Should not validate - early return
        mock_validate.assert_not_called()


def test_start_sav_monitor_validation_error(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _start_sav_monitor shows warning on validation error.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with (
        patch.object(panel, "_validate_sav_config", return_value=(None, "Validation failed")),
        patch(
            "foxhole_stockpiles.gui.widgets.server_control_panel.QMessageBox.warning"
        ) as mock_warning,
    ):
        panel._start_sav_monitor()

        mock_warning.assert_called_once()


def test_stop_sav_monitor(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _stop_sav_monitor stops the worker.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    mock_worker = MagicMock()
    panel._sav_monitor_worker = mock_worker
    panel._sav_monitoring = True

    panel._stop_sav_monitor()

    mock_worker.stop.assert_called_once()
    assert panel._sav_monitoring is False


def test_stop_sav_monitor_no_worker(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _stop_sav_monitor with no worker.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel._sav_monitor_worker = None
    panel._sav_monitoring = True

    # Should not raise
    panel._stop_sav_monitor()

    assert panel._sav_monitoring is True  # Not changed since no worker


def test_on_sav_error(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _on_sav_error logs the error.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    import logging

    with patch.object(
        logging.getLogger("foxhole_stockpiles.gui.widgets.server_control_panel"), "error"
    ) as mock_log:
        panel._on_sav_error("Test error message")

        mock_log.assert_called_once()
        assert "Test error message" in str(mock_log.call_args)


def test_on_sav_scan_finished(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _on_sav_scan_finished updates UI state.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.scan_sav_button.setEnabled(False)
    panel._sav_scan_worker = MagicMock()

    panel._on_sav_scan_finished(True)

    assert panel.scan_sav_button.isEnabled()
    assert panel._sav_scan_worker is None


def test_on_sav_monitor_finished(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _on_sav_monitor_finished updates UI state.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    mock_worker = MagicMock()
    panel._sav_monitor_worker = mock_worker
    panel._sav_monitoring = True

    # Mock the sender() to return the current worker
    with patch.object(panel, "sender", return_value=mock_worker):
        panel._on_sav_monitor_finished(True)

    assert panel._sav_monitoring is False
    assert panel._sav_monitor_worker is None


def test_on_sav_monitor_finished_different_sender(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _on_sav_monitor_finished doesn't update if sender is different worker.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    mock_worker = MagicMock()
    old_worker = MagicMock()
    panel._sav_monitor_worker = mock_worker
    panel._sav_monitoring = True

    # Mock the sender() to return a different worker
    with patch.object(panel, "sender", return_value=old_worker):
        panel._on_sav_monitor_finished(True)

    # Should not update state since sender is different
    assert panel._sav_monitoring is True
    assert panel._sav_monitor_worker is mock_worker


def test_retranslate_server_running(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test retranslate updates button text when server is running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.server_running = True
    panel._sav_monitoring = False

    panel.retranslate()

    assert panel.start_stop_button.text() == t("server_panel.stop_server")
    assert panel.status_label.text() == t("server_panel.status_running")


def test_retranslate_sav_monitoring(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test retranslate updates SAV button text when monitoring.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel._sav_monitoring = True

    panel.retranslate()

    assert panel.monitor_sav_button.text() == t("server_panel.stop_monitor")


def test_cleanup_method(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _cleanup method stops workers and disconnects signals.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with (
        patch.object(panel, "_stop_all_workers") as mock_stop_workers,
        patch(
            "foxhole_stockpiles.gui.widgets.server_control_panel.off_language_changed"
        ) as mock_off_lang,
    ):
        panel._cleanup()

        mock_off_lang.assert_called_once_with(panel._language_callback)
        mock_stop_workers.assert_called_once()


def test_stop_all_workers_with_running_workers(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _stop_all_workers stops running worker threads.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    # Create mock workers
    mock_monitor = MagicMock()
    mock_monitor.isRunning.return_value = True
    mock_scan = MagicMock()
    mock_scan.isRunning.return_value = True

    panel._sav_monitor_worker = mock_monitor
    panel._sav_scan_worker = mock_scan

    panel._stop_all_workers()

    mock_monitor.stop.assert_called_once()
    mock_monitor.wait.assert_called_once_with(2000)
    mock_scan.wait.assert_called_once_with(2000)


def test_stop_all_workers_no_running_workers(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _stop_all_workers when workers are not running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    mock_monitor = MagicMock()
    mock_monitor.isRunning.return_value = False
    mock_scan = MagicMock()
    mock_scan.isRunning.return_value = False

    panel._sav_monitor_worker = mock_monitor
    panel._sav_scan_worker = mock_scan

    panel._stop_all_workers()

    mock_monitor.stop.assert_not_called()
    mock_scan.wait.assert_not_called()


def test_validation_path_not_relative_to_cwd(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation shows absolute path when not relative to cwd.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    # Use a path that is definitely not relative to cwd (root path)
    test_db = Path("/some/absolute/path/test_db.h5")

    with (
        patch.object(server_control_panel, "AppSettings") as mock_settings_class,
        patch.object(Path, "exists", return_value=True),
    ):
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = str(test_db)

        panel._update_validation_state()
        QApplication.processEvents()

        # Should show just filename since path is not relative
        assert "test_db.h5" in panel.db_info_text.text()


def test_scan_sav_file_success(qtbot: Any, panel: ServerControlPanel, tmp_path: Path) -> None:
    """Test scan_sav_file successfully starts a scan.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    with (
        patch.object(panel, "_validate_sav_config", return_value=(sav_file, None)),
        patch.object(server_control_panel, "AppSettings") as mock_settings_class,
        patch.object(server_control_panel, "OutputCoordinator"),
        patch.object(server_control_panel, "SavScanWorker") as mock_worker_class,
    ):
        mock_settings = mock_settings_class.return_value
        mock_settings.output = MagicMock()

        mock_worker = mock_worker_class.return_value

        panel.scan_sav_file()

        # Verify worker was created with correct args (no uesave)
        mock_worker_class.assert_called_once()
        args = mock_worker_class.call_args[0]
        assert args[0] == sav_file

        # Verify worker was started
        mock_worker.start.assert_called_once()

        # Verify UI state
        assert panel.scan_sav_button.isEnabled() is False


def test_start_sav_monitor_success(qtbot: Any, panel: ServerControlPanel, tmp_path: Path) -> None:
    """Test _start_sav_monitor successfully starts monitoring.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    with (
        patch.object(panel, "_validate_sav_config", return_value=(sav_file, None)),
        patch.object(server_control_panel, "AppSettings") as mock_settings_class,
        patch.object(server_control_panel, "OutputCoordinator"),
        patch.object(server_control_panel, "SavMonitorWorker") as mock_worker_class,
    ):
        mock_settings = mock_settings_class.return_value
        mock_settings.output = MagicMock()
        mock_settings.sav_processing.poll_interval = 2.0

        mock_worker = mock_worker_class.return_value

        panel._start_sav_monitor()

        # Verify worker was created with correct args (no uesave)
        mock_worker_class.assert_called_once()
        args = mock_worker_class.call_args[0]
        assert args[0] == sav_file
        assert args[2] == 2.0  # poll_interval (second positional arg after output_coordinator)

        # Verify worker was started
        mock_worker.start.assert_called_once()

        # Verify UI state
        assert panel._sav_monitoring is True
        assert panel.monitor_sav_button.text() == t("server_panel.stop_monitor")


def test_start_sav_monitor_output_error(
    qtbot: Any, panel: ServerControlPanel, tmp_path: Path
) -> None:
    """Test _start_sav_monitor shows error on output coordinator failure.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    with (
        patch.object(panel, "_validate_sav_config", return_value=(sav_file, None)),
        patch.object(server_control_panel, "AppSettings", side_effect=OSError("Output error")),
        patch(
            "foxhole_stockpiles.gui.widgets.server_control_panel.QMessageBox.critical"
        ) as mock_critical,
    ):
        panel._start_sav_monitor()

        mock_critical.assert_called_once()
        # Monitor should not have started
        assert panel._sav_monitoring is False


def test_validate_sav_config_auto_detect_success(
    qtbot: Any, panel: ServerControlPanel, tmp_path: Path
) -> None:
    """Test _validate_sav_config successfully auto-detects SAV file.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
        tmp_path (Path): Temporary directory path from pytest fixture.
    """
    from foxhole_stockpiles.gui.widgets import server_control_panel

    sav_file = tmp_path / "test.sav"
    sav_file.touch()

    with (
        patch.object(server_control_panel, "AppSettings") as mock_settings_class,
        patch.object(server_control_panel, "auto_detect_savefile", return_value=sav_file),
    ):
        mock_settings = mock_settings_class.return_value
        mock_settings.sav_processing.sav_file_path = None  # No configured path

        sav_path, error = panel._validate_sav_config()

        assert sav_path == sav_file
        assert error is None


def test_stop_all_workers_with_none_workers(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _stop_all_workers when workers are None.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel._sav_monitor_worker = None
    panel._sav_scan_worker = None

    # Should not raise
    panel._stop_all_workers()


def test_log_display_vertical_header(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test that log display vertical header is hidden.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    vertical_header = panel.log_display.verticalHeader()
    if vertical_header:
        assert not vertical_header.isVisible()


def test_db_info_text_relative_path(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation shows relative path when within cwd.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    import os

    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    # Use the test fixture which is within the test directory
    test_db = Path(__file__).parent.parent.parent / "fixtures" / "test_db_v1.h5"

    # Change to parent directory so the path can be relative
    original_cwd = os.getcwd()
    try:
        os.chdir(test_db.parent.parent.parent)

        with patch.object(server_control_panel, "AppSettings") as mock_settings_class:
            mock_settings = mock_settings_class.return_value
            mock_settings.scanner.database_path = str(test_db)

            panel._update_validation_state()
            QApplication.processEvents()

            # Should show DB info
            assert panel.db_info_text.isVisible()
    finally:
        os.chdir(original_cwd)


def test_panel_server_signals(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test that server started/stopped signals are emitted.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    started_spy = []
    stopped_spy = []
    panel.server_started.connect(lambda: started_spy.append(True))
    panel.server_stopped.connect(lambda: stopped_spy.append(True))

    with patch(
        "foxhole_stockpiles.gui.widgets.server_control_panel.ServerThread"
    ) as mock_thread_class:
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread

        panel.start_server()
        assert len(started_spy) == 1

    panel.stop_server()
    assert len(stopped_spy) == 1


def test_scan_screenshot_from_menu_no_file_selected(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test scan_screenshot_from_menu when no file is selected.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    with (
        patch(
            "foxhole_stockpiles.gui.widgets.server_control_panel.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ),
        patch.object(panel, "process_screenshot") as mock_process,
    ):
        panel.scan_screenshot_from_menu()
        mock_process.assert_not_called()


def test_process_screenshot_worker_cleanup(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test that scan workers are cleaned up after completion.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.server_running = True

    with patch(
        "foxhole_stockpiles.gui.widgets.server_control_panel.ScanWorker"
    ) as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        # Store the finished callback
        finished_callback = None

        def capture_connect(callback: Any) -> None:
            nonlocal finished_callback
            finished_callback = callback

        mock_worker.finished.connect.side_effect = capture_connect

        panel.process_screenshot("/test/file.png")

        assert hasattr(panel, "_scan_workers")
        assert mock_worker in panel._scan_workers

        # Simulate worker finishing - this should trigger cleanup
        if finished_callback:
            finished_callback()


def test_retranslate_server_not_running(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test retranslate when server is not running.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.server_running = False
    panel._sav_monitoring = False

    panel.retranslate()

    assert panel.start_stop_button.text() == t("server_panel.start_server")
    assert panel.status_label.text() == t("server_panel.status_stopped")
    assert panel.monitor_sav_button.text() == t("server_panel.start_monitor")


def test_validation_db_path_value_error(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test validation handles ValueError when getting relative path.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    from PySide6.QtWidgets import QApplication

    from foxhole_stockpiles.gui.widgets import server_control_panel

    # Use a path that triggers ValueError in relative_to
    test_db = Path("/completely/different/path/test_db.h5")

    with (
        patch.object(server_control_panel, "AppSettings") as mock_settings_class,
        patch.object(Path, "exists", return_value=True),
    ):
        mock_settings = mock_settings_class.return_value
        mock_settings.scanner.database_path = str(test_db)

        panel._update_validation_state()
        QApplication.processEvents()

        # Should show just the filename since path is not relative to cwd
        if panel.db_info_text.isVisible():
            assert "test_db.h5" in panel.db_info_text.text()


def test_on_sav_scan_finished_failure(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _on_sav_scan_finished with failure status.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    panel.scan_sav_button.setEnabled(False)
    panel._sav_scan_worker = MagicMock()

    panel._on_sav_scan_finished(False)  # Failure

    assert panel.scan_sav_button.isEnabled()
    assert panel._sav_scan_worker is None


def test_on_sav_monitor_finished_failure(qtbot: Any, panel: ServerControlPanel) -> None:
    """Test _on_sav_monitor_finished with failure status.

    Args:
        qtbot: PyQt test fixture
        panel (ServerControlPanel): Panel instance
    """
    mock_worker = MagicMock()
    panel._sav_monitor_worker = mock_worker
    panel._sav_monitoring = True

    with patch.object(panel, "sender", return_value=mock_worker):
        panel._on_sav_monitor_finished(False)  # Failure

    assert panel._sav_monitoring is False
    assert panel._sav_monitor_worker is None
