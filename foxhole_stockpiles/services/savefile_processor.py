"""Service to process Foxhole save files for stockpile data."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator, OutputResponse
from foxhole_stockpiles.services.sav_parser import SaveFileBusyError, parse_save

logger = logging.getLogger(__name__)

OnChanged = Callable[[list[Stockpile]], None]


class SaveFileProcessor:
    """Processes save files and optionally watches for changes."""

    def __init__(
        self,
        file_path: Path,
        output_coordinator: OutputCoordinator,
        poll_interval: float = 1.0,
        emit_all_on_start: bool = False,
    ) -> None:
        """Initialize the processor.

        Args:
            file_path (Path): Path to the save file to monitor.
            output_coordinator (OutputCoordinator): Output coordinator for handlers.
            poll_interval (float): Polling interval in seconds.
            emit_all_on_start (bool): Emit all stockpiles on first run.
        """
        self._file_path = file_path
        self._output_coordinator = output_coordinator
        self._poll_interval = poll_interval
        self._emit_all_on_start = emit_all_on_start
        self._last_mtime: float | None = None
        self._running = False
        self._stop_requested = False
        self._primed = False
        self._baseline_pending = False
        # The output handlers' response from the most recent routed batch,
        # surfaced so the GUI can show it. None when nothing was routed.
        self.last_output: OutputResponse = None

        # Track stockpiles by key -> timestamp string for change detection
        self._stockpile_cache: dict[str, str] = {}

    @property
    def file_path(self) -> Path:
        """The monitored file path."""
        return self._file_path

    @property
    def poll_interval(self) -> float:
        """The polling interval."""
        return self._poll_interval

    @poll_interval.setter
    def poll_interval(self, value: float) -> None:
        """Set the polling interval."""
        self._poll_interval = value

    @staticmethod
    def _timestamp_key(timestamp: datetime) -> str:
        """Normalize a timestamp to a stable UTC string for change detection.

        Naive datetimes are assumed to be UTC; aware datetimes are converted to
        UTC so the same instant always yields the same key regardless of the
        original offset.

        Args:
            timestamp (datetime): The stockpile timestamp.

        Returns:
            str: A UTC ISO-8601 string usable as a cache key.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC).isoformat()

    async def _output_results(self, stockpiles: list[Stockpile]) -> None:
        """Output stockpiles through the handler pipeline in a single call.

        The full list is handed to the output coordinator at once; each handler
        decides how to treat the batch (e.g. the webhook handler may group by
        location internally).

        Args:
            stockpiles (list[Stockpile]): List of stockpiles to output.
        """
        if not stockpiles:
            return

        logger.info("Sending %d stockpile(s) to output handlers", len(stockpiles))
        self.last_output = await self._output_coordinator.handle_output(stockpiles)

    def _detect_changes(
        self, stockpiles: list[Stockpile]
    ) -> tuple[list[Stockpile], list[Stockpile], list[str]]:
        """Detect which stockpiles have changed.

        Uses timestamp string comparison for change detection since fs-sav
        doesn't expose raw UE ticks.

        Args:
            stockpiles (list[Stockpile]): Current stockpiles.

        Returns:
            tuple[list[Stockpile], list[Stockpile], list[str]]: The
                (updated_stockpiles, new_stockpiles, removed_keys) triple.
        """
        updated: list[Stockpile] = []
        new: list[Stockpile] = []
        current_keys: set[str] = set()

        for stockpile in stockpiles:
            key = stockpile.to_key()
            current_keys.add(key)
            timestamp_str = self._timestamp_key(stockpile.timestamp)
            cached_timestamp = self._stockpile_cache.get(key)

            if cached_timestamp is None:
                # New stockpile
                new.append(stockpile)
                self._stockpile_cache[key] = timestamp_str
            elif cached_timestamp != timestamp_str:
                # Timestamp changed
                updated.append(stockpile)
                self._stockpile_cache[key] = timestamp_str
            # else: unchanged, skip

        # Find removed stockpiles
        removed_keys = [k for k in self._stockpile_cache if k not in current_keys]
        for key in removed_keys:
            del self._stockpile_cache[key]

        return updated, new, removed_keys

    async def _process_file(self, is_initial: bool = False) -> list[Stockpile]:
        """Process the save file and output changed stockpiles.

        Args:
            is_initial (bool): Whether this is the initial load.

        Returns:
            list[Stockpile]: List of changed stockpiles that were output.
        """
        logger.info("Processing file...")
        stockpiles = await asyncio.to_thread(parse_save, self._file_path)

        if not stockpiles:
            logger.info("No stockpiles found in save file.")
            return []

        if is_initial and self._emit_all_on_start:
            return await self._output_initial_load(stockpiles)

        return await self._output_changes(stockpiles)

    async def _process_file_keep_watching(self, is_initial: bool = False) -> list[Stockpile]:
        """Process the save file, logging a failure so that watching goes on.

        Args:
            is_initial (bool): Whether this is the initial load.

        Returns:
            list[Stockpile]: List of changed stockpiles that were output, empty on failure.
        """
        try:
            return await self._process_file(is_initial=is_initial)
        except SaveFileBusyError as e:
            # The game was writing the file: forget its mtime so the next poll retries.
            logger.warning("Save file busy, retrying on the next poll: %s", e)
            self._last_mtime = None
        except Exception as e:  # noqa: BLE001 - a failed read must not stop the watcher
            logger.error("Error processing file: %s", e)
        return []

    async def _output_initial_load(self, stockpiles: list[Stockpile]) -> list[Stockpile]:
        """Remember every stockpile and output them all.

        Args:
            stockpiles (list[Stockpile]): The stockpiles in the file.

        Returns:
            list[Stockpile]: The same stockpiles.
        """
        for stockpile in stockpiles:
            self._stockpile_cache[stockpile.to_key()] = self._timestamp_key(stockpile.timestamp)

        logger.info("Initial load: %d stockpile(s)", len(stockpiles))
        await self._output_results(stockpiles)
        return stockpiles

    async def _output_changes(self, stockpiles: list[Stockpile]) -> list[Stockpile]:
        """Output what changed since the last read.

        Args:
            stockpiles (list[Stockpile]): The stockpiles in the file.

        Returns:
            list[Stockpile]: The new and updated stockpiles.
        """
        updated, new, removed = self._detect_changes(stockpiles)

        if not (updated or new or removed):
            logger.debug("No changes detected.")
            return []

        if new:
            logger.info("New: %d stockpile(s)", len(new))
        if updated:
            logger.info("Updated: %d stockpile(s)", len(updated))
        if removed:
            logger.info("Removed: %d stockpile(s)", len(removed))

        changed_stockpiles = new + updated
        if changed_stockpiles:
            await self._output_results(changed_stockpiles)

        return changed_stockpiles

    async def run_once(self) -> list[Stockpile]:
        """Process the file once without monitoring.

        Returns:
            list[Stockpile]: List of stockpiles found.

        Raises:
            Exception: If processing the save file fails.
        """
        return await self._process_file(is_initial=True)

    async def prime(self) -> int | None:
        """Fill the change-detection cache from the file without emitting anything.

        Call before ``run`` to report only changes made after this point. When
        the read fails, the next successful read in ``run`` becomes the baseline
        instead of reporting every stockpile as new.

        Returns:
            int | None: The number of stockpiles cached, or None if the file is
                missing or could not be read.
        """
        self._primed = True
        if not self._file_path.exists():
            return None

        self._baseline_pending = True
        try:
            self._last_mtime = self._file_path.stat().st_mtime
            stockpiles = await asyncio.to_thread(parse_save, self._file_path)
        except SaveFileBusyError as e:
            logger.warning("Save file busy, retrying on the next poll: %s", e)
            self._last_mtime = None
            return None
        except Exception as e:  # noqa: BLE001 - the watch loop retries on the next write
            logger.warning("Could not read initial state: %s", e)
            return None

        self._stockpile_cache = {
            stockpile.to_key(): self._timestamp_key(stockpile.timestamp) for stockpile in stockpiles
        }
        self._baseline_pending = False
        logger.info("Cached %d stockpile(s). Monitoring for changes...", len(stockpiles))
        return len(stockpiles)

    async def _poll_once(self, on_changed: OnChanged | None) -> None:
        """Process the file if it was modified since the last read.

        Args:
            on_changed (OnChanged | None): Called with the changed stockpiles.
        """
        if not self._file_path.exists():
            return

        current_mtime = self._file_path.stat().st_mtime
        if self._last_mtime is not None and current_mtime <= self._last_mtime:
            return

        if self._baseline_pending:
            await self.prime()
            return

        self._last_mtime = current_mtime
        await self._process_and_notify(is_initial=False, on_changed=on_changed)

    async def _process_and_notify(self, is_initial: bool, on_changed: OnChanged | None) -> None:
        """Process the file and pass any changed stockpiles to the callback.

        Args:
            is_initial (bool): Whether this is the initial load.
            on_changed (OnChanged | None): Called with the changed stockpiles.
        """
        changed = await self._process_file_keep_watching(is_initial=is_initial)
        if changed and on_changed is not None:
            on_changed(changed)

    async def run(self, on_changed: OnChanged | None = None) -> None:
        """Run the file processor in watch mode.

        A processor that was primed skips the initial load.

        Args:
            on_changed (OnChanged | None): Called with the changed stockpiles
                after they were routed to the outputs. Defaults to None.
        """
        if self._stop_requested:
            self._stop_requested = False
            return

        self._running = True
        logger.info("Watching: %s", self._file_path)
        logger.info("Poll interval: %ss", self._poll_interval)

        try:
            if not self._primed and self._file_path.exists():
                self._last_mtime = self._file_path.stat().st_mtime
                await self._process_and_notify(is_initial=True, on_changed=on_changed)

            while self._running:
                try:
                    await asyncio.sleep(self._poll_interval)
                    if self._running:
                        await self._poll_once(on_changed)
                except asyncio.CancelledError:
                    break
                except Exception as e:  # noqa: BLE001 - keep the poll loop alive on any error
                    logger.error("Processor error: %s", e)
        finally:
            self._running = False
            self._stop_requested = False

    def stop(self) -> None:
        """Stop the monitor, including one whose ``run`` has not started yet."""
        self._running = False
        self._stop_requested = True
