"""Service to process Foxhole save files for stockpile data."""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.sav_parser import parse_save

logger = logging.getLogger(__name__)


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

    @property
    def is_running(self) -> bool:
        """Check if processor is running in watch mode."""
        return self._running

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
        await self._output_coordinator.handle_output(stockpiles)

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

    async def _process_file(
        self, is_initial: bool = False, suppress_errors: bool = True
    ) -> list[Stockpile]:
        """Process the save file and output changed stockpiles.

        Args:
            is_initial (bool): Whether this is the initial load.
            suppress_errors (bool): If True, log and swallow processing errors
                (watch mode keeps running). If False, re-raise so the caller can
                surface the failure. Defaults to True.

        Returns:
            list[Stockpile]: List of changed stockpiles that were output.

        Raises:
            Exception: If processing fails and suppress_errors is False.
        """
        logger.info("Processing file...")

        try:
            stockpiles = await asyncio.to_thread(parse_save, self._file_path)

            if not stockpiles:
                logger.info("No stockpiles found in save file.")
                return []

            # On initial load with emit_all_on_start, output everything
            if is_initial and self._emit_all_on_start:
                # Initialize cache
                for stockpile in stockpiles:
                    self._stockpile_cache[stockpile.to_key()] = self._timestamp_key(
                        stockpile.timestamp
                    )

                logger.info("Initial load: %d stockpile(s)", len(stockpiles))
                await self._output_results(stockpiles)
                return stockpiles

            # Detect changes
            updated, new, removed = self._detect_changes(stockpiles)

            total_changes = len(updated) + len(new) + len(removed)
            if total_changes == 0:
                logger.debug("No changes detected.")
                return []

            # Log changes
            if new:
                logger.info("New: %d stockpile(s)", len(new))
            if updated:
                logger.info("Updated: %d stockpile(s)", len(updated))
            if removed:
                logger.info("Removed: %d stockpile(s)", len(removed))

            # Output changed stockpiles (new + updated)
            changed_stockpiles = new + updated
            if changed_stockpiles:
                await self._output_results(changed_stockpiles)

            return changed_stockpiles

        except Exception as e:
            if not suppress_errors:
                raise
            logger.error("Error processing file: %s", e)
            return []

    async def run_once(self) -> list[Stockpile]:
        """Process the file once without monitoring.

        Returns:
            list[Stockpile]: List of stockpiles found.

        Raises:
            Exception: If processing the save file fails.
        """
        return await self._process_file(is_initial=True, suppress_errors=False)

    async def run(self) -> None:
        """Run the file processor in watch mode."""
        self._running = True
        logger.info("Watching: %s", self._file_path)
        logger.info("Poll interval: %ss", self._poll_interval)

        try:
            # Process once immediately (initial load)
            if self._file_path.exists():
                self._last_mtime = self._file_path.stat().st_mtime
                await self._process_file(is_initial=True)

            while self._running:
                try:
                    await asyncio.sleep(self._poll_interval)

                    if not self._file_path.exists():
                        continue

                    current_mtime = self._file_path.stat().st_mtime

                    # Only process if file was modified
                    if self._last_mtime is None or current_mtime > self._last_mtime:
                        self._last_mtime = current_mtime
                        await self._process_file(is_initial=False)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Processor error: %s", e)
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
