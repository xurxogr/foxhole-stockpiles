"""Tests for ScanWorker."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from foxhole_stockpiles.gui.utils.scan_worker import ScanWorker


@pytest.fixture
def mock_scanner_client() -> MagicMock:
    """Create a mock scanner client.

    Returns:
        MagicMock: Mock scanner client
    """
    client = MagicMock()
    client.scan_screenshot.return_value = (True, "Success")
    return client


def test_scan_worker_initialization(qtbot: Any, mock_scanner_client: MagicMock) -> None:
    """Test ScanWorker initialization.

    Args:
        qtbot: PyQt test fixture
        mock_scanner_client (MagicMock): Mock scanner client
    """
    filepath = "/test/screenshot.png"
    worker = ScanWorker(mock_scanner_client, filepath)

    assert worker.scanner_client == mock_scanner_client
    assert worker.filepath == filepath


def test_scan_worker_run(qtbot: Any, mock_scanner_client: MagicMock) -> None:
    """Test ScanWorker run method.

    Args:
        qtbot: PyQt test fixture
        mock_scanner_client (MagicMock): Mock scanner client
    """
    filepath = "/test/screenshot.png"
    worker = ScanWorker(mock_scanner_client, filepath)

    # Track if finished signal was emitted
    finished_called = False

    def on_finished() -> None:
        nonlocal finished_called
        finished_called = True

    worker.scan_finished.connect(on_finished)

    # Start the worker
    worker.start()

    # Wait for the worker to finish
    qtbot.waitUntil(lambda: finished_called, timeout=5000)

    # Verify scan_screenshot was called
    mock_scanner_client.scan_screenshot.assert_called_once_with(filepath)
    assert finished_called


def test_scan_worker_thread_safety(qtbot: Any, mock_scanner_client: MagicMock) -> None:
    """Test ScanWorker runs in separate thread.

    Args:
        qtbot: PyQt test fixture
        mock_scanner_client (MagicMock): Mock scanner client
    """
    import threading

    main_thread_id = threading.current_thread().ident
    worker_thread_id = None

    def capture_thread_id(*args: Any, **kwargs: Any) -> None:
        nonlocal worker_thread_id
        worker_thread_id = threading.current_thread().ident

    mock_scanner_client.scan_screenshot.side_effect = capture_thread_id

    filepath = "/test/screenshot.png"
    worker = ScanWorker(mock_scanner_client, filepath)

    finished_called = False

    def on_finished() -> None:
        nonlocal finished_called
        finished_called = True

    worker.scan_finished.connect(on_finished)
    worker.start()

    qtbot.waitUntil(lambda: finished_called, timeout=5000)

    # Verify it ran in a different thread
    assert worker_thread_id is not None
    assert worker_thread_id != main_thread_id


def test_scan_worker_run_directly(qtbot: Any, mock_scanner_client: MagicMock) -> None:
    """Test ScanWorker run method directly (for coverage).

    Args:
        qtbot: PyQt test fixture
        mock_scanner_client (MagicMock): Mock scanner client
    """
    filepath = "/test/screenshot.png"
    worker = ScanWorker(mock_scanner_client, filepath)

    # Track signal emission
    signals_received: list[bool] = []
    worker.scan_finished.connect(lambda: signals_received.append(True))

    # Call run() directly instead of start() to ensure coverage
    worker.run()

    # Verify scan_screenshot was called
    mock_scanner_client.scan_screenshot.assert_called_once_with(filepath)

    # Verify finished signal was emitted
    assert len(signals_received) == 1
