"""Tests for the SaveFileProcessor service.

The real ``.sav`` parsing (``parse_save``) is patched out so these tests cover
the processor's own logic: change detection, output fan-out, one-shot
processing, and watch-mode polling.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor

_PARSE = "foxhole_stockpiles.services.savefile_processor.parse_save"


class FakeCoordinator:
    """Records every ``handle_output`` call for assertions."""

    def __init__(self) -> None:
        """Initialize the recorded-calls list."""
        self.calls: list[list[Stockpile]] = []

    async def handle_output(self, stockpiles: list[Stockpile]) -> None:
        """Record a copy of the routed stockpiles."""
        self.calls.append(list(stockpiles))


def make_stockpile(
    name: str = "Public",
    hex_name: str = "TerminusHex",
    x: float = 0.1,
    y: float = 0.2,
    ts: datetime | None = None,
    type_: StockpileType = StockpileType.SEAPORT,
) -> Stockpile:
    """Build a Stockpile for tests."""
    return Stockpile(
        name=name,
        type=type_,
        hex=hex_name,
        coords=StockpileCoords(x=x, y=y),
        timestamp=ts or datetime(2026, 1, 1, 12, 0, 0),
    )


def make_processor(tmp_path: Path, **kwargs: object) -> tuple[SaveFileProcessor, FakeCoordinator]:
    """Build a processor over a real temp file with a fake coordinator."""
    f = tmp_path / "MapData.sav"
    f.write_text("x")
    coord = FakeCoordinator()
    proc = SaveFileProcessor(f, coord, **kwargs)  # type: ignore[arg-type]
    return proc, coord


class TestInitAndProperties:
    """Constructor and property behavior."""

    def test_defaults(self, tmp_path: Path) -> None:
        """Defaults: not running, poll 1.0s, file path exposed."""
        proc, _ = make_processor(tmp_path)
        assert proc.file_path == tmp_path / "MapData.sav"
        assert proc.poll_interval == 1.0
        assert proc.is_running is False

    def test_poll_interval_setter(self, tmp_path: Path) -> None:
        """poll_interval can be reassigned."""
        proc, _ = make_processor(tmp_path)
        proc.poll_interval = 2.5
        assert proc.poll_interval == 2.5

    def test_stop_sets_not_running(self, tmp_path: Path) -> None:
        """stop() clears the running flag."""
        proc, _ = make_processor(tmp_path)
        proc._running = True
        proc.stop()
        assert proc.is_running is False


class TestTimestampKey:
    """The UTC-normalizing change-detection key."""

    def test_naive_is_assumed_utc(self, tmp_path: Path) -> None:
        """A naive datetime is treated as UTC."""
        proc, _ = make_processor(tmp_path)
        key = proc._timestamp_key(datetime(2026, 1, 1, 12, 0, 0))
        assert key == "2026-01-01T12:00:00+00:00"

    def test_aware_is_converted_to_utc(self, tmp_path: Path) -> None:
        """An aware datetime is converted to UTC (same instant, same key)."""
        proc, _ = make_processor(tmp_path)
        plus_two = timezone(timedelta(hours=2))
        aware = datetime(2026, 1, 1, 14, 0, 0, tzinfo=plus_two)
        naive_utc = datetime(2026, 1, 1, 12, 0, 0)
        assert proc._timestamp_key(aware) == proc._timestamp_key(naive_utc)


class TestDetectChanges:
    """Change detection against the internal cache."""

    def test_first_seen_are_new(self, tmp_path: Path) -> None:
        """All stockpiles are 'new' on first detection."""
        proc, _ = make_processor(tmp_path)
        updated, new, removed = proc._detect_changes([make_stockpile()])
        assert len(new) == 1
        assert updated == []
        assert removed == []

    def test_unchanged_skipped(self, tmp_path: Path) -> None:
        """A stockpile with an unchanged timestamp is neither new nor updated."""
        proc, _ = make_processor(tmp_path)
        sp = make_stockpile()
        proc._detect_changes([sp])
        updated, new, removed = proc._detect_changes([sp])
        assert new == []
        assert updated == []
        assert removed == []

    def test_changed_timestamp_is_update(self, tmp_path: Path) -> None:
        """A newer timestamp on the same key is an update."""
        proc, _ = make_processor(tmp_path)
        proc._detect_changes([make_stockpile(ts=datetime(2026, 1, 1, 12, 0, 0))])
        updated, new, removed = proc._detect_changes(
            [make_stockpile(ts=datetime(2026, 1, 1, 13, 0, 0))]
        )
        assert len(updated) == 1
        assert new == []

    def test_missing_stockpile_is_removed(self, tmp_path: Path) -> None:
        """A previously-seen key absent from the new set is reported removed."""
        proc, _ = make_processor(tmp_path)
        proc._detect_changes([make_stockpile()])
        updated, new, removed = proc._detect_changes([])
        assert len(removed) == 1
        assert proc._stockpile_cache == {}


class TestOutputResults:
    """Fan-out of results: the full batch goes to the handler in one call."""

    async def test_empty_no_call(self, tmp_path: Path) -> None:
        """No stockpiles → no handler call."""
        proc, coord = make_processor(tmp_path)
        await proc._output_results([])
        assert coord.calls == []

    async def test_all_stockpiles_in_single_call(self, tmp_path: Path) -> None:
        """Every stockpile is sent to the handler in one batched call."""
        proc, coord = make_processor(tmp_path)
        stockpiles = [make_stockpile(x=0.1, y=0.2), make_stockpile(x=0.9, y=0.8)]
        await proc._output_results(stockpiles)
        assert len(coord.calls) == 1
        assert coord.calls[0] == stockpiles


class TestRunOnce:
    """One-shot processing."""

    async def test_emit_all_on_start_outputs_everything(self, tmp_path: Path) -> None:
        """emit_all_on_start outputs every stockpile and primes the cache."""
        proc, coord = make_processor(tmp_path, emit_all_on_start=True)
        sp = make_stockpile()
        with patch(_PARSE, return_value=[sp]):
            result = await proc.run_once()
        assert len(result) == 1
        assert len(coord.calls) == 1
        assert proc._stockpile_cache  # primed

    async def test_no_stockpiles_returns_empty(self, tmp_path: Path) -> None:
        """An empty parse result yields no output."""
        proc, coord = make_processor(tmp_path, emit_all_on_start=True)
        with patch(_PARSE, return_value=[]):
            result = await proc.run_once()
        assert result == []
        assert coord.calls == []

    async def test_without_emit_all_uses_change_detection(self, tmp_path: Path) -> None:
        """Without emit_all, the initial run still emits the new stockpiles."""
        proc, coord = make_processor(tmp_path, emit_all_on_start=False)
        with patch(_PARSE, return_value=[make_stockpile()]):
            result = await proc.run_once()
        assert len(result) == 1
        assert len(coord.calls) == 1

    async def test_propagates_errors(self, tmp_path: Path) -> None:
        """run_once re-raises parse failures (suppress_errors=False)."""
        proc, _ = make_processor(tmp_path)
        with (
            patch(_PARSE, side_effect=RuntimeError("boom")),
            contextlib.suppress(RuntimeError),
        ):
            await proc.run_once()
            raise AssertionError("expected RuntimeError")


class TestProcessFile:
    """Direct _process_file behaviors."""

    async def test_no_changes_returns_empty(self, tmp_path: Path) -> None:
        """A second identical process detects no changes."""
        proc, _ = make_processor(tmp_path, emit_all_on_start=False)
        sp = make_stockpile()
        with patch(_PARSE, return_value=[sp]):
            await proc._process_file(is_initial=False)
            second = await proc._process_file(is_initial=False)
        assert second == []

    async def test_suppresses_errors(self, tmp_path: Path) -> None:
        """With suppress_errors, a parse failure returns [] instead of raising."""
        proc, _ = make_processor(tmp_path)
        with patch(_PARSE, side_effect=RuntimeError("boom")):
            result = await proc._process_file(is_initial=False, suppress_errors=True)
        assert result == []


class TestRunWatchMode:
    """Watch-mode polling loop."""

    async def test_initial_load_then_stop(self, tmp_path: Path) -> None:
        """run() does the initial load, marks running, and stops cleanly."""
        proc, coord = make_processor(tmp_path, poll_interval=0.01, emit_all_on_start=True)
        with patch(_PARSE, return_value=[make_stockpile()]):
            task = asyncio.create_task(proc.run())
            await asyncio.sleep(0.05)
            assert proc.is_running is True
            proc.stop()
            await asyncio.wait_for(task, timeout=2)
        assert proc.is_running is False
        assert len(coord.calls) >= 1

    async def test_reprocesses_on_modification(self, tmp_path: Path) -> None:
        """A newer file mtime triggers a re-process of the save."""
        proc, coord = make_processor(tmp_path, poll_interval=0.01, emit_all_on_start=True)
        sp1 = make_stockpile(ts=datetime(2026, 1, 1, 12, 0, 0))
        sp2 = make_stockpile(ts=datetime(2026, 1, 1, 13, 0, 0))
        state = {"n": 0}

        def fake_parse(_path: Path) -> list[Stockpile]:
            state["n"] += 1
            return [sp1] if state["n"] == 1 else [sp2]

        with patch(_PARSE, side_effect=fake_parse):
            task = asyncio.create_task(proc.run())
            await asyncio.sleep(0.03)  # initial load caches sp1
            future = proc.file_path.stat().st_mtime + 1000
            os.utime(proc.file_path, (future, future))
            await asyncio.sleep(0.05)  # loop sees newer mtime → reprocess
            proc.stop()
            await asyncio.wait_for(task, timeout=2)
        assert state["n"] >= 2
        assert len(coord.calls) >= 2

    async def test_missing_file_skips_initial_load(self, tmp_path: Path) -> None:
        """run() tolerates a missing file (no initial load, loop continues)."""
        coord = FakeCoordinator()
        missing = tmp_path / "nope.sav"
        proc = SaveFileProcessor(missing, coord, poll_interval=0.01)  # type: ignore[arg-type]
        with patch(_PARSE, return_value=[make_stockpile()]) as parse:
            task = asyncio.create_task(proc.run())
            await asyncio.sleep(0.04)
            proc.stop()
            await asyncio.wait_for(task, timeout=2)
        parse.assert_not_called()
        assert coord.calls == []

    async def test_cancellation_breaks_loop(self, tmp_path: Path) -> None:
        """Cancelling the task is caught and exits the loop cleanly."""
        proc, _ = make_processor(tmp_path, poll_interval=0.01, emit_all_on_start=True)
        with patch(_PARSE, return_value=[make_stockpile()]):
            task = asyncio.create_task(proc.run())
            await asyncio.sleep(0.03)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
        assert proc.is_running is False
