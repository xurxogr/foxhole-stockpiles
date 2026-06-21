"""Tests for LocalScanWorker (capture/file scan + screenshot saving)."""

from typing import Any
from unittest.mock import MagicMock, patch

from foxhole_stockpiles.gui.utils.capture_scan_worker import LocalScanWorker

_MODULE = "foxhole_stockpiles.gui.utils.capture_scan_worker"


def test_capture_success_saves_with_stockpile(qtbot: Any) -> None:
    """A successful capture scan emits the stockpile and saves the screenshot."""
    service = MagicMock()
    stockpile = MagicMock()
    service.scan.return_value = stockpile

    worker = LocalScanWorker(service, capture=True, screenshots_folder="shots")
    finished: list[Any] = []
    errors: list[str] = []
    worker.scan_finished.connect(finished.append)
    worker.scan_error.connect(errors.append)

    with (
        patch(f"{_MODULE}.capture_window", return_value=b"PNG") as mock_capture,
        patch(f"{_MODULE}.save_screenshot") as mock_save,
    ):
        worker.run()  # run synchronously

    mock_capture.assert_called_once()
    service.scan.assert_called_once_with(b"PNG")
    mock_save.assert_called_once_with(b"PNG", "shots", stockpile)
    assert finished == [stockpile]
    assert errors == []


def test_capture_failed_scan_still_saves(qtbot: Any) -> None:
    """A failed capture scan still saves the screenshot (with no stockpile)."""
    service = MagicMock()
    service.scan.side_effect = ValueError("boom")

    worker = LocalScanWorker(service, capture=True, screenshots_folder="shots")
    errors: list[str] = []
    worker.scan_error.connect(errors.append)

    with (
        patch(f"{_MODULE}.capture_window", return_value=b"PNG"),
        patch(f"{_MODULE}.save_screenshot") as mock_save,
    ):
        worker.run()

    # Saved even though the scan raised, with stockpile=None.
    mock_save.assert_called_once_with(b"PNG", "shots", None)
    assert errors == ["boom"]


def test_capture_no_folder_does_not_save(qtbot: Any) -> None:
    """With no screenshots_folder configured, nothing is saved."""
    service = MagicMock()
    service.scan.return_value = MagicMock()

    worker = LocalScanWorker(service, capture=True, screenshots_folder="")

    with (
        patch(f"{_MODULE}.capture_window", return_value=b"PNG"),
        patch(f"{_MODULE}.save_screenshot") as mock_save,
    ):
        worker.run()

    mock_save.assert_not_called()


def test_file_scan_does_not_capture_or_save(qtbot: Any) -> None:
    """A file scan neither captures nor saves a screenshot."""
    service = MagicMock()
    stockpile = MagicMock()
    service.scan.return_value = stockpile

    worker = LocalScanWorker(service, filepath="/tmp/x.png", screenshots_folder="shots")
    finished: list[Any] = []
    worker.scan_finished.connect(finished.append)

    with (
        patch(f"{_MODULE}.capture_window") as mock_capture,
        patch(f"{_MODULE}.save_screenshot") as mock_save,
    ):
        worker.run()

    mock_capture.assert_not_called()
    mock_save.assert_not_called()
    service.scan.assert_called_once_with("/tmp/x.png")
    assert finished == [stockpile]
