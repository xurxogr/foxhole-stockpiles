"""Tests for the clipboard worker threads.

``run()`` is invoked directly (not via ``start()``) so the worker bodies execute
synchronously in the test thread with an async-mocked service.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from foxhole_stockpiles.gui.utils.clipboard_workers import (
    ClipboardMonitorWorker,
    ClipboardScanWorker,
)
from foxhole_stockpiles.models.stockpile import Stockpile


def _collect(worker: Any) -> tuple[list[Any], list[str], list[bool]]:
    """Wire signal collectors and return their backing lists."""
    found: list[Any] = []
    errors: list[str] = []
    finished: list[bool] = []
    worker.stockpile_found.connect(found.append)
    worker.error.connect(errors.append)
    worker.finished.connect(finished.append)
    return found, errors, finished


class TestClipboardScanWorker:
    """One-shot clipboard scan worker."""

    def test_success(self, qtbot: Any) -> None:
        """A successful scan emits the stockpile and finished(True)."""
        service = MagicMock()
        service.scan_once = AsyncMock(return_value=Stockpile())
        worker = ClipboardScanWorker(service)
        found, errors, finished = _collect(worker)
        worker.run()
        assert len(found) == 1
        assert finished == [True]
        assert errors == []

    def test_failure(self, qtbot: Any) -> None:
        """A scan exception emits error and finished(False)."""
        service = MagicMock()
        service.scan_once = AsyncMock(side_effect=RuntimeError("boom"))
        worker = ClipboardScanWorker(service)
        _found, errors, finished = _collect(worker)
        worker.run()
        assert errors
        assert finished == [False]


class TestClipboardMonitorWorker:
    """Continuous clipboard monitor worker."""

    def test_stop_before_run_exits_immediately(self, qtbot: Any) -> None:
        """Stopping before run exits the loop with finished(True)."""
        service = MagicMock()
        service.poll = AsyncMock(return_value=None)
        worker = ClipboardMonitorWorker(service, poll_interval=0.001)
        _found, _errors, finished = _collect(worker)
        worker.stop()
        worker.run()
        assert finished == [True]

    def test_emits_new_export_then_stops(self, qtbot: Any) -> None:
        """A polled stockpile is emitted; the loop then stops."""
        service = MagicMock()
        stockpile = Stockpile()
        worker = ClipboardMonitorWorker(service, poll_interval=0.001)

        async def poll() -> Stockpile:
            worker._should_stop = True
            return stockpile

        service.poll = poll
        found, _errors, finished = _collect(worker)
        worker.run()
        assert found == [stockpile]
        assert finished == [True]

    def test_loop_error_is_logged_and_loop_ends(self, qtbot: Any) -> None:
        """A poll error inside the loop is swallowed; the loop still ends cleanly."""
        service = MagicMock()
        worker = ClipboardMonitorWorker(service, poll_interval=0.001)

        async def poll() -> Stockpile:
            worker._should_stop = True
            raise RuntimeError("transient")

        service.poll = poll
        _found, _errors, finished = _collect(worker)
        worker.run()
        assert finished == [True]
