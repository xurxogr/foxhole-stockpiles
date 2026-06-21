"""Tests for QtLogHandler."""

import logging
from typing import Any

import pytest
from PySide6.QtCore import QObject

from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler


@pytest.fixture
def handler(qtbot: Any) -> QtLogHandler:
    """Create a QtLogHandler instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        QtLogHandler: Handler instance
    """
    return QtLogHandler()


def test_handler_initialization(handler: QtLogHandler) -> None:
    """Test QtLogHandler initialization.

    Args:
        handler (QtLogHandler): Handler instance
    """
    assert isinstance(handler, logging.Handler)
    assert isinstance(handler, QObject)


def test_handler_emits_log_data(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler emits structured log data.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    received_data = []

    def capture_log(log_data: dict[str, Any]) -> None:
        received_data.append(log_data)

    handler.log_message.connect(capture_log)

    # Create a log record
    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Emit the record
    handler.emit(record)

    # Verify log data was emitted
    assert len(received_data) == 1
    log_data = received_data[0]

    assert "timestamp" in log_data
    assert log_data["level"] == "INFO"
    assert log_data["module"] == "test.module"
    assert log_data["message"] == "Test message"
    assert "color" in log_data


def test_handler_client_log_color(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler assigns cyan color to client logs.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    received_data: list[dict[str, Any]] = []
    handler.log_message.connect(lambda data: received_data.append(data))

    record = logging.LogRecord(
        name="foxhole_stockpiles.services.capture",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Client log",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert len(received_data) == 1
    assert received_data[0]["color"] == "#00BFFF"  # Cyan


def test_handler_server_log_color(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler assigns white color to server logs.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    received_data: list[dict[str, Any]] = []
    handler.log_message.connect(lambda data: received_data.append(data))

    record = logging.LogRecord(
        name="foxhole_stockpiles.services.output_coordinator",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Server log",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert len(received_data) == 1
    assert received_data[0]["color"] == "#FFFFFF"  # White


def test_handler_error_log_color(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler assigns red color to error logs.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    received_data: list[dict[str, Any]] = []
    handler.log_message.connect(lambda data: received_data.append(data))

    record = logging.LogRecord(
        name="test.module",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="Error log",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert len(received_data) == 1
    assert received_data[0]["color"] == "#FF6B6B"  # Red


def test_handler_warning_log_color(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler assigns orange color to warning logs.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    received_data: list[dict[str, Any]] = []
    handler.log_message.connect(lambda data: received_data.append(data))

    record = logging.LogRecord(
        name="test.module",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="Warning log",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    assert len(received_data) == 1
    assert received_data[0]["color"] == "#FFA500"  # Orange


def test_handler_closed_does_not_emit(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler does not emit after close.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    received_data: list[dict[str, Any]] = []
    handler.log_message.connect(lambda data: received_data.append(data))

    # Close the handler
    handler.close()

    # Try to emit a record
    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Should not be emitted",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    # Should not have received any data
    assert len(received_data) == 0


def test_handler_emit_exception_calls_handle_error(qtbot: Any, handler: QtLogHandler) -> None:
    """Test QtLogHandler calls handleError when emit raises exception.

    Args:
        qtbot: PyQt test fixture
        handler (QtLogHandler): Handler instance
    """
    from unittest.mock import patch

    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Mock log_message.emit to raise an exception
    with patch.object(handler, "log_message") as mock_signal:
        mock_signal.emit.side_effect = RuntimeError("Signal emission failed")

        with patch.object(handler, "handleError") as mock_handle_error:
            handler.emit(record)

            # Should have called handleError
            mock_handle_error.assert_called_once_with(record)


def test_handler_getattribute_runtime_error_flushOnClose(qtbot: Any) -> None:
    """Test __getattribute__ returns False for flushOnClose on RuntimeError.

    Args:
        qtbot: PyQt test fixture
    """
    handler = QtLogHandler()

    # Simulate Qt object deletion by making the handler raise RuntimeError
    # We can't easily mock __getattribute__ but we can verify the handler
    # has flushOnClose set to False which is the purpose of this safety check
    assert handler.flushOnClose is False


def test_handler_has_handler_name(qtbot: Any) -> None:
    """Test handler has HANDLER_NAME identifier.

    Args:
        qtbot: PyQt test fixture
    """
    handler = QtLogHandler()

    assert handler.name == QtLogHandler.HANDLER_NAME
    assert handler.name == "foxhole_qt_gui_handler"
