"""Tests for the SAV monitor worker."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from PySide6.QtCore import QThread

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.gui.utils.sav_monitor_worker import SavMonitorWorker
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.services.sav_parser import SaveFileBusyError
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor


def _stockpile(ts: datetime) -> Stockpile:
    """Build a stockpile with a fixed location and the given timestamp."""
    return Stockpile(
        name="Public",
        type=StockpileType.SEAPORT,
        hex="TerminusHex",
        coords=StockpileCoords(x=0.1, y=0.2),
        timestamp=ts,
    )


def _monitor_worker(sav: Path) -> SavMonitorWorker:
    """Build a monitor worker holding a real processor on a fake coordinator."""
    coord = MagicMock()
    coord.handle_output = AsyncMock(return_value=None)
    worker = SavMonitorWorker(sav, coord, poll_interval=0.001)
    worker._processor = SaveFileProcessor(
        file_path=sav,
        output_coordinator=coord,
        poll_interval=0.001,
        emit_all_on_start=False,
    )
    return worker


def _drive_monitor(
    worker: SavMonitorWorker,
    sav: Path,
    parse: list[Any],
    touch_on_polls: set[int],
    polls: int,
) -> list[Any]:
    """Run the monitor loop for a scripted number of polls.

    Args:
        worker (SavMonitorWorker): The worker under test.
        sav (Path): The watched file.
        parse (list[Any]): Successive parse results (or exceptions to raise).
        touch_on_polls (set[int]): Poll numbers on which the file gets a newer mtime.
        polls (int): Number of polls to run before the worker is stopped.

    Returns:
        list[Any]: Every list emitted through ``stockpiles_changed``.
    """
    state = {"n": 0}

    async def fake_sleep(_seconds: float) -> None:
        state["n"] += 1
        if state["n"] in touch_on_polls:
            future = sav.stat().st_mtime + 1000
            os.utime(sav, (future, future))
        if state["n"] > polls:
            worker.stop()

    changed: list[Any] = []
    worker.stockpiles_changed.connect(changed.append)
    parser = MagicMock(side_effect=parse)

    with (
        patch("foxhole_stockpiles.services.savefile_processor.parse_save", parser),
        patch("asyncio.sleep", fake_sleep),
    ):
        asyncio.run(worker._run_monitor())

    return changed


class TestSavMonitorRunMonitor:
    """Direct coverage of the async monitoring loop."""

    def test_no_processor_returns(self) -> None:
        """_run_monitor returns immediately when no processor is set."""
        worker = SavMonitorWorker(Path("x.sav"), MagicMock(), poll_interval=0.001)
        worker._processor = None
        asyncio.run(worker._run_monitor())

    def test_processes_change_then_stops(self, tmp_path: Path) -> None:
        """The loop caches the initial state, then emits on a modification."""
        sav = tmp_path / "World_MapData.sav"
        sav.write_text("x")
        worker = _monitor_worker(sav)

        sp1 = _stockpile(datetime(2026, 1, 1, 12, 0, 0))
        sp2 = _stockpile(datetime(2026, 1, 1, 13, 0, 0))

        changed = _drive_monitor(worker, sav, parse=[[sp1], [sp2]], touch_on_polls={1}, polls=2)

        assert changed == [[sp2]]

    def test_non_utc_timestamp_is_not_a_change(self, tmp_path: Path) -> None:
        """Re-reading the same instant in a non-UTC offset emits nothing."""
        sav = tmp_path / "World_MapData.sav"
        sav.write_text("x")
        worker = _monitor_worker(sav)
        stockpile = _stockpile(datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))))

        changed = _drive_monitor(
            worker, sav, parse=[[stockpile], [stockpile]], touch_on_polls={1}, polls=2
        )

        assert changed == []

    def test_busy_initial_read_retries_without_reporting_everything(self, tmp_path: Path) -> None:
        """A busy first read is retried silently; only later changes are emitted."""
        sav = tmp_path / "World_MapData.sav"
        sav.write_text("x")
        worker = _monitor_worker(sav)
        sp1 = _stockpile(datetime(2026, 1, 1, 12, 0, 0))
        sp2 = _stockpile(datetime(2026, 1, 1, 13, 0, 0))

        changed = _drive_monitor(
            worker,
            sav,
            parse=[SaveFileBusyError("busy"), [sp1], [sp2]],
            touch_on_polls={2},
            polls=3,
        )

        assert changed == [[sp2]]

    def test_failed_initial_read_does_not_report_everything(self, tmp_path: Path) -> None:
        """After a failed first read, the next write sets the baseline silently."""
        sav = tmp_path / "World_MapData.sav"
        sav.write_text("x")
        worker = _monitor_worker(sav)
        sp1 = _stockpile(datetime(2026, 1, 1, 12, 0, 0))
        sp2 = _stockpile(datetime(2026, 1, 1, 13, 0, 0))

        changed = _drive_monitor(
            worker,
            sav,
            parse=[RuntimeError("corrupt"), [sp1], [sp2]],
            touch_on_polls={1, 2},
            polls=3,
        )

        assert changed == [[sp2]]


class TestSavMonitorWorker:
    """Tests for SavMonitorWorker."""

    def test_initialization(self) -> None:
        """Test SavMonitorWorker initialization."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()
        poll_interval = 2.5

        worker = SavMonitorWorker(sav_path, output_coordinator, poll_interval)

        assert worker._sav_path == sav_path
        assert worker._output_coordinator == output_coordinator
        assert worker._poll_interval == poll_interval
        assert worker._should_stop is False
        assert worker._processor is None
        assert isinstance(worker, QThread)

    def test_initialization_default_poll_interval(self) -> None:
        """Test SavMonitorWorker initialization with default poll interval."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        worker = SavMonitorWorker(sav_path, output_coordinator)

        assert worker._poll_interval == 1.0

    def test_stop(self) -> None:
        """Test stopping the monitor worker."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        worker = SavMonitorWorker(sav_path, output_coordinator)
        mock_processor = MagicMock()
        worker._processor = mock_processor

        worker.stop()

        assert worker._should_stop is True
        mock_processor.stop.assert_called_once()

    def test_stop_no_processor(self) -> None:
        """Test stopping the monitor worker when no processor exists."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        worker = SavMonitorWorker(sav_path, output_coordinator)

        # Should not raise
        worker.stop()

        assert worker._should_stop is True

    def test_run_runtime_error(self) -> None:
        """Test monitor run with runtime error."""
        sav_path = Path("/nonexistent/file.sav")
        output_coordinator = MagicMock()

        with patch(
            "foxhole_stockpiles.gui.utils.sav_monitor_worker.SaveFileProcessor",
            side_effect=RuntimeError("Processor init failed"),
        ):
            worker = SavMonitorWorker(sav_path, output_coordinator)

            error_spy: list[str] = []
            finished_spy: list[bool] = []
            worker.error.connect(lambda msg: error_spy.append(msg))
            worker.monitor_finished.connect(lambda success: finished_spy.append(success))

            worker.run()

            assert len(error_spy) == 1
            assert "Processor init failed" in error_spy[0]
            assert len(finished_spy) == 1
            assert finished_spy[0] is False

    def test_run_generic_exception(self) -> None:
        """Test monitor run with generic exception."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        with patch(
            "foxhole_stockpiles.gui.utils.sav_monitor_worker.SaveFileProcessor",
            side_effect=ValueError("Init error"),
        ):
            worker = SavMonitorWorker(sav_path, output_coordinator)

            error_spy: list[str] = []
            finished_spy: list[bool] = []
            worker.error.connect(lambda msg: error_spy.append(msg))
            worker.monitor_finished.connect(lambda success: finished_spy.append(success))

            worker.run()

            assert len(error_spy) == 1
            assert "Error monitoring SAV file" in error_spy[0]
            assert "Init error" in error_spy[0]
            assert len(finished_spy) == 1
            assert finished_spy[0] is False

    def test_run_success(self) -> None:
        """Test successful monitor run."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        with (
            patch(
                "foxhole_stockpiles.gui.utils.sav_monitor_worker.SaveFileProcessor"
            ) as mock_processor_class,
            patch(
                "foxhole_stockpiles.gui.utils.sav_monitor_worker.asyncio.run"
            ) as mock_asyncio_run,
        ):
            worker = SavMonitorWorker(sav_path, output_coordinator)

            finished_spy: list[bool] = []
            worker.monitor_finished.connect(lambda success: finished_spy.append(success))

            worker.run()

            # Verify processor was created with correct arguments
            mock_processor_class.assert_called_once_with(
                file_path=sav_path,
                output_coordinator=output_coordinator,
                poll_interval=1.0,
                emit_all_on_start=False,
            )

            # Verify asyncio.run was called with _run_monitor coroutine
            mock_asyncio_run.assert_called_once()

            # Verify signals
            assert len(finished_spy) == 1
            assert finished_spy[0] is True
