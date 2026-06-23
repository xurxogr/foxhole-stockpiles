"""Tests for LoggingTab."""

from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections.logging import LoggingSettings
from foxhole_stockpiles.gui.widgets.config_tabs.logging_tab import LoggingTab


@pytest.fixture
def logging_tab(qtbot: Any) -> LoggingTab:
    """Create a LoggingTab instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        LoggingTab: Tab instance
    """
    tab = LoggingTab()
    qtbot.addWidget(tab)
    return tab


def test_logging_tab_initialization(logging_tab: LoggingTab) -> None:
    """Test LoggingTab initialization.

    Args:
        logging_tab: LoggingTab instance
    """
    assert logging_tab.root_level_combo is not None
    assert logging_tab.log_format_input is not None
    assert logging_tab.date_format_input is not None
    assert logging_tab.rotate_logs_input is not None
    assert logging_tab.log_file_input is not None
    assert logging_tab.custom_logger_rows is not None
    assert len(logging_tab.custom_logger_rows) == 0  # No custom loggers by default


def test_logging_tab_default_values(logging_tab: LoggingTab) -> None:
    """Test default values are set correctly.

    Args:
        logging_tab: LoggingTab instance
    """
    # Root level should be INFO by default
    assert logging_tab.root_level_combo.currentText() == "INFO"
    # No custom loggers by default
    assert len(logging_tab.custom_logger_rows) == 0


def test_logging_tab_root_level_options(logging_tab: LoggingTab) -> None:
    """Test root level combo box has correct options.

    Args:
        logging_tab: LoggingTab instance
    """
    levels = [
        logging_tab.root_level_combo.itemText(i)
        for i in range(logging_tab.root_level_combo.count())
    ]
    assert "DEBUG" in levels
    assert "INFO" in levels
    assert "WARNING" in levels
    assert "ERROR" in levels
    assert "CRITICAL" in levels


def test_logging_tab_set_values(logging_tab: LoggingTab) -> None:
    """Test setting values from settings object.

    Args:
        logging_tab: LoggingTab instance
    """
    settings = LoggingSettings(
        log_level="DEBUG",
        log_format="%(levelname)s - %(message)s",
        date_format="%Y-%m-%d",
        rotate_logs=True,
        log_file="/var/log/app.log",
        loggers={"uvicorn": "WARNING", "foxhole_stockpiles": "DEBUG"},
    )

    logging_tab.set_values(settings)

    # Check root level
    assert logging_tab.root_level_combo.currentText() == "DEBUG"

    # Check other fields
    assert logging_tab.log_format_input.text() == "%(levelname)s - %(message)s"
    assert logging_tab.date_format_input.text() == "%Y-%m-%d"
    assert logging_tab.rotate_logs_input.isChecked()
    assert logging_tab.log_file_input.text() == "/var/log/app.log"

    # Check custom loggers were added
    assert len(logging_tab.custom_logger_rows) == 2


def test_logging_tab_set_values_no_log_file(logging_tab: LoggingTab) -> None:
    """Test setting values with no log file.

    Args:
        logging_tab: LoggingTab instance
    """
    settings = LoggingSettings(log_file=None)

    logging_tab.set_values(settings)

    assert logging_tab.log_file_input.text() == ""


def test_logging_tab_get_values(logging_tab: LoggingTab) -> None:
    """Test getting values from widgets.

    Args:
        logging_tab: LoggingTab instance
    """
    # Set root level
    logging_tab.root_level_combo.setCurrentText("ERROR")

    logging_tab.log_format_input.setText("%(asctime)s - %(message)s")
    logging_tab.date_format_input.setText("%H:%M:%S")
    logging_tab.rotate_logs_input.setChecked(False)
    logging_tab.log_file_input.setText("/tmp/test.log")

    settings = logging_tab.get_values()

    assert settings.log_level == "ERROR"
    assert settings.log_format == "%(asctime)s - %(message)s"
    assert settings.date_format == "%H:%M:%S"
    assert not settings.rotate_logs
    assert settings.log_file == "/tmp/test.log"


def test_logging_tab_get_values_empty_log_file(logging_tab: LoggingTab) -> None:
    """Test getting values with empty log file.

    Args:
        logging_tab: LoggingTab instance
    """
    logging_tab.log_file_input.setText("")

    settings = logging_tab.get_values()

    assert settings.log_file is None


def test_logging_tab_get_values_whitespace_log_file(logging_tab: LoggingTab) -> None:
    """Test getting values with whitespace-only log file.

    Args:
        logging_tab: LoggingTab instance
    """
    logging_tab.log_file_input.setText("   ")

    settings = logging_tab.get_values()

    # Whitespace should be preserved (validation happens in pydantic)
    assert settings.log_file == "   "


def test_logging_tab_browse_log_file(qtbot: Any, logging_tab: LoggingTab) -> None:
    """Test browse log file button.

    Args:
        qtbot: PyQt test fixture
        logging_tab: LoggingTab instance
    """
    test_path = "/path/to/logfile.log"

    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.logging_tab.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "Log Files (*.log)")

        logging_tab._browse_log_file()

        assert logging_tab.log_file_input.text() == test_path
        mock_dialog.assert_called_once()


def test_logging_tab_browse_log_file_cancel(qtbot: Any, logging_tab: LoggingTab) -> None:
    """Test browse log file cancel.

    Args:
        qtbot: PyQt test fixture
        logging_tab: LoggingTab instance
    """
    original_text = logging_tab.log_file_input.text()

    with patch(
        "foxhole_stockpiles.gui.widgets.config_tabs.logging_tab.QFileDialog.getSaveFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        logging_tab._browse_log_file()

        # Should not change text
        assert logging_tab.log_file_input.text() == original_text


def test_logging_tab_set_values_default_settings(logging_tab: LoggingTab) -> None:
    """Test setting values with default settings object.

    Args:
        logging_tab: LoggingTab instance
    """
    settings = LoggingSettings()

    logging_tab.set_values(settings)

    assert logging_tab.root_level_combo.currentText() == settings.log_level.upper()
    assert logging_tab.log_format_input.text() == settings.log_format
    assert logging_tab.date_format_input.text() == settings.date_format


def test_logging_tab_log_level_case_insensitive(logging_tab: LoggingTab) -> None:
    """Test log level is converted to uppercase.

    Args:
        logging_tab: LoggingTab instance
    """
    settings = LoggingSettings(log_level="debug")

    logging_tab.set_values(settings)

    assert logging_tab.root_level_combo.currentText() == "DEBUG"


def test_logging_tab_rotate_logs_checkbox(logging_tab: LoggingTab) -> None:
    """Test rotate logs checkbox behavior.

    Args:
        logging_tab: LoggingTab instance
    """
    logging_tab.rotate_logs_input.setChecked(True)
    assert logging_tab.rotate_logs_input.isChecked()

    logging_tab.rotate_logs_input.setChecked(False)
    assert not logging_tab.rotate_logs_input.isChecked()


def test_logging_tab_all_log_levels_selectable(logging_tab: LoggingTab) -> None:
    """Test all log levels can be selected.

    Args:
        logging_tab: LoggingTab instance
    """
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        logging_tab.root_level_combo.setCurrentText(level)
        assert logging_tab.root_level_combo.currentText() == level


def test_logging_tab_get_values_preserves_format_strings(logging_tab: LoggingTab) -> None:
    """Test that format strings are preserved exactly.

    Args:
        logging_tab: LoggingTab instance
    """
    custom_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    custom_date = "%Y-%m-%d %H:%M:%S"

    logging_tab.log_format_input.setText(custom_format)
    logging_tab.date_format_input.setText(custom_date)

    settings = logging_tab.get_values()

    assert settings.log_format == custom_format
    assert settings.date_format == custom_date


def test_logging_tab_empty_format_strings(logging_tab: LoggingTab) -> None:
    """Test with empty format strings.

    Args:
        logging_tab: LoggingTab instance
    """
    logging_tab.log_format_input.setText("")
    logging_tab.date_format_input.setText("")

    settings = logging_tab.get_values()

    # Empty strings should be preserved
    assert settings.log_format == ""
    assert settings.date_format == ""


def test_logging_tab_add_custom_logger(logging_tab: LoggingTab) -> None:
    """Test adding a custom logger.

    Args:
        logging_tab: LoggingTab instance
    """
    initial_count = len(logging_tab.custom_logger_rows)

    logging_tab._on_add_logger()

    assert len(logging_tab.custom_logger_rows) == initial_count + 1
    new_row = logging_tab.custom_logger_rows[-1]
    assert new_row.get_logger_name() == ""
    assert new_row.get_level() == "INFO"


def test_logging_tab_remove_custom_logger(logging_tab: LoggingTab) -> None:
    """Test removing a custom logger.

    Args:
        logging_tab: LoggingTab instance
    """
    # Add a custom logger
    logging_tab._on_add_logger()
    new_row = logging_tab.custom_logger_rows[-1]
    new_row.name_input.setText("test.logger")

    # Remove it
    new_row._on_remove()

    # Row should be marked as removed
    assert new_row.is_removed()

    # Get values should not include removed row
    settings = logging_tab.get_values()
    assert "test.logger" not in settings.loggers


def test_logging_tab_custom_loggers_in_get_values(logging_tab: LoggingTab) -> None:
    """Test that custom loggers are included in get_values.

    Args:
        logging_tab: LoggingTab instance
    """
    # Add custom loggers
    logging_tab._on_add_logger()
    row1 = logging_tab.custom_logger_rows[-1]
    row1.name_input.setText("uvicorn")
    row1.level_combo.setCurrentText("WARNING")

    logging_tab._on_add_logger()
    row2 = logging_tab.custom_logger_rows[-1]
    row2.name_input.setText("foxhole_stockpiles")
    row2.level_combo.setCurrentText("DEBUG")

    settings = logging_tab.get_values()

    assert settings.loggers == {"uvicorn": "WARNING", "foxhole_stockpiles": "DEBUG"}


def test_logging_tab_empty_logger_name_ignored(logging_tab: LoggingTab) -> None:
    """Test that loggers with empty names are ignored.

    Args:
        logging_tab: LoggingTab instance
    """
    # Add a logger with empty name
    logging_tab._on_add_logger()

    settings = logging_tab.get_values()

    # Empty name should not be in loggers dict
    assert "" not in settings.loggers


def test_logging_tab_custom_logger_level_options(logging_tab: LoggingTab) -> None:
    """Test custom logger level combo box has correct options.

    Args:
        logging_tab: LoggingTab instance
    """
    logging_tab._on_add_logger()
    row = logging_tab.custom_logger_rows[-1]

    levels = [row.level_combo.itemText(i) for i in range(row.level_combo.count())]
    assert "DEBUG" in levels
    assert "INFO" in levels
    assert "WARNING" in levels
    assert "ERROR" in levels
    assert "CRITICAL" in levels


def test_logging_tab_all_widgets_visible(logging_tab: LoggingTab) -> None:
    """All logging widgets are present and not hidden (no config-level gating).

    Args:
        logging_tab: LoggingTab instance
    """
    # Use isHidden() instead of isVisible() since parent widget is not shown
    assert not logging_tab.root_level_combo.isHidden()
    assert not logging_tab._log_format_label.isHidden()
    assert not logging_tab.log_format_input.isHidden()
    assert not logging_tab._date_format_label.isHidden()
    assert not logging_tab.date_format_input.isHidden()
    assert not logging_tab._rotate_logs_label.isHidden()
    assert not logging_tab.rotate_logs_input.isHidden()
    assert not logging_tab._log_file_label.isHidden()
    assert not logging_tab._log_file_widget.isHidden()
    assert not logging_tab._custom_loggers_header.isHidden()
    assert not logging_tab._loggers_scroll.isHidden()
