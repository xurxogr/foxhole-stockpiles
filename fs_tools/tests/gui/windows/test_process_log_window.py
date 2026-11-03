"""What the windows running a long process share: showing its logs while it runs."""

import logging
from collections.abc import Iterator
from typing import Any

import pytest

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.sections import LoggingSettings
from fs_tools.gui.windows.process_log_window import ProcessLogWindow

_MODULE_NAME = "some_tool"


@pytest.fixture
def window(qtbot: Any) -> Iterator[ProcessLogWindow]:
    """Build a window, removing its handler from the root logger afterwards.

    Args:
        qtbot (Any): Qt test helper.

    Yields:
        ProcessLogWindow: The window.
    """
    settings = AppSettings(logging=LoggingSettings(log_level="WARNING"))
    level_before = logging.getLogger().level
    window = ProcessLogWindow(settings=settings, log_module=_MODULE_NAME)
    qtbot.addWidget(window)
    yield window
    logging.getLogger().removeHandler(window.log_handler)
    logging.getLogger().setLevel(level_before)


def test_handler_uses_the_configured_level(window: ProcessLogWindow) -> None:
    """The display shows what the configuration asks for."""
    assert window.log_handler.level == logging.WARNING


def test_logs_reach_the_display_only_while_capturing(window: ProcessLogWindow) -> None:
    """Between two processes the window does not listen to the application logs."""
    logger = logging.getLogger("test_process_log_window")

    logger.warning("before")
    assert window.log_display.rowCount() == 0

    window.start_log_capture()
    assert logging.getLogger().level == logging.WARNING
    logger.warning("during")
    assert window.log_display.rowCount() == 1

    window.stop_log_capture()
    logger.warning("after")
    assert window.log_display.rowCount() == 1


def test_clearing_empties_the_display(window: ProcessLogWindow) -> None:
    """Clearing removes every row."""
    window.log_info("something")

    window.clear_logs()

    assert window.log_display.rowCount() == 0


@pytest.mark.parametrize(
    ("add_row", "level"),
    [
        (ProcessLogWindow.log_success, "INFO"),
        (ProcessLogWindow.log_info, "INFO"),
        (ProcessLogWindow.log_warning, "WARNING"),
        (ProcessLogWindow.log_error, "ERROR"),
    ],
)
def test_process_messages_are_shown_with_their_level(
    window: ProcessLogWindow, add_row: Any, level: str
) -> None:
    """Each kind of message adds one row saying its level, module and text."""
    add_row(window, "the message")

    items = [window.log_display.item(0, column) for column in range(4)]
    row = [item.text() for item in items if item is not None]
    assert level in row
    assert _MODULE_NAME in row
    assert "the message" in row
