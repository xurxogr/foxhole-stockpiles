"""Tests for the one-shot clipboard scan worker.

``run()`` is invoked directly (not via ``start()``) so the worker bodies execute
synchronously in the test thread with an async-mocked service.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from foxhole_stockpiles.gui.utils.clipboard_scan_worker import ClipboardScanWorker
from foxhole_stockpiles.models.stockpile import Stockpile


def _collect(worker: Any) -> tuple[list[Any], list[str], list[bool]]:
    """Wire signal collectors and return their backing lists."""
    found: list[Any] = []
    errors: list[str] = []
    finished: list[bool] = []
    worker.stockpile_found.connect(found.append)
    worker.error.connect(errors.append)
    worker.scan_finished.connect(finished.append)
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
