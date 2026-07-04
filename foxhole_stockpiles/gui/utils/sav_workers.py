"""Worker threads for SAV file processing."""

import asyncio
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.sav_parser import parse_save
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor

logger = logging.getLogger(__name__)


class SavScanWorker(QThread):
    """Worker thread for one-time SAV file scanning."""

    finished = Signal(bool)  # True = success, False = failure
    error = Signal(str)  # Error message
    progress = Signal(str)  # Progress message
    stockpiles_found = Signal(list)  # List of Stockpile objects
    output_response = Signal(object)  # OutputResponse (dict | list[str] | None)

    def __init__(
        self,
        sav_path: Path,
        output_coordinator: OutputCoordinator,
    ) -> None:
        """Initialize the SAV scan worker.

        Args:
            sav_path (Path): Path to the .sav file to scan.
            output_coordinator (OutputCoordinator): Output coordinator for handlers.
        """
        super().__init__()
        self._sav_path = sav_path
        self._output_coordinator = output_coordinator

    def run(self) -> None:
        """Run the scan in background thread."""
        try:
            logger.info("Processing file: %s", self._sav_path)
            self.progress.emit(f"Processing: {self._sav_path.name}")

            # Create processor and run once
            processor = SaveFileProcessor(
                file_path=self._sav_path,
                output_coordinator=self._output_coordinator,
                emit_all_on_start=True,
            )

            # Run the async method in an event loop
            stockpiles = asyncio.run(processor.run_once())

            self.stockpiles_found.emit(stockpiles)
            self.output_response.emit(processor.last_output)
            self.finished.emit(True)

        except RuntimeError as e:
            self.error.emit(str(e))
            self.finished.emit(False)
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            self.error.emit(f"Error processing SAV file: {e}")
            self.finished.emit(False)


class SavMonitorWorker(QThread):
    """Worker thread for continuous SAV file monitoring."""

    finished = Signal(bool)  # True = stopped normally, False = error
    error = Signal(str)  # Error message
    progress = Signal(str)  # Progress/status message
    stockpiles_changed = Signal(list)  # List of changed Stockpile objects
    output_response = Signal(object)  # OutputResponse (dict | list[str] | None)

    def __init__(
        self,
        sav_path: Path,
        output_coordinator: OutputCoordinator,
        poll_interval: float = 1.0,
    ) -> None:
        """Initialize the SAV monitor worker.

        Args:
            sav_path (Path): Path to the .sav file to monitor.
            output_coordinator (OutputCoordinator): Output coordinator for handlers.
            poll_interval (float): Polling interval in seconds.
        """
        super().__init__()
        self._sav_path = sav_path
        self._output_coordinator = output_coordinator
        self._poll_interval = poll_interval
        self._should_stop = False
        self._processor: SaveFileProcessor | None = None

    def stop(self) -> None:
        """Request the monitor to stop."""
        self._should_stop = True
        if self._processor:
            self._processor.stop()

    def run(self) -> None:
        """Run the monitor in background thread."""
        try:
            logger.info("Starting monitor for: %s", self._sav_path)
            logger.info("Poll interval: %ss", self._poll_interval)

            # Create processor
            self._processor = SaveFileProcessor(
                file_path=self._sav_path,
                output_coordinator=self._output_coordinator,
                poll_interval=self._poll_interval,
                emit_all_on_start=False,  # Don't emit on first read for monitoring
            )

            # Run the monitor - this blocks until stopped
            asyncio.run(self._run_monitor())

            logger.info("Monitor stopped")
            self.finished.emit(True)

        except RuntimeError as e:
            self.error.emit(str(e))
            self.finished.emit(False)
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            self.error.emit(f"Error monitoring SAV file: {e}")
            self.finished.emit(False)

    async def _run_monitor(self) -> None:
        """Run the monitoring loop with change detection callback."""
        if not self._processor:
            return

        # Initial read to populate cache (no output)
        if self._sav_path.exists():
            self._processor._last_mtime = self._sav_path.stat().st_mtime
            # Process to populate cache without emitting
            try:
                stockpiles = parse_save(self._sav_path)
                for stockpile in stockpiles:
                    self._processor._stockpile_cache[stockpile.to_key()] = (
                        stockpile.timestamp.isoformat()
                    )
                logger.info("Cached %d stockpile(s). Monitoring for changes...", len(stockpiles))
                self.progress.emit(f"Monitoring {len(stockpiles)} stockpile(s)...")
            except Exception as e:  # noqa: BLE001 - keep monitoring even if the initial read fails
                logger.warning("Could not read initial state: %s", e)

        self._processor._running = True

        while self._processor._running and not self._should_stop:
            try:
                await asyncio.sleep(self._processor._poll_interval)

                if self._should_stop:
                    break

                if not self._sav_path.exists():
                    continue

                current_mtime = self._sav_path.stat().st_mtime

                # Only process if file was modified
                if (
                    self._processor._last_mtime is None
                    or current_mtime > self._processor._last_mtime
                ):
                    self._processor._last_mtime = current_mtime
                    changed = await self._processor._process_file(is_initial=False)
                    if changed:
                        self.stockpiles_changed.emit(changed)
                        self.output_response.emit(self._processor.last_output)

            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001 - keep the poll loop alive on any error
                logger.error("Monitor error: %s", e)

        self._processor._running = False
