"""Worker thread for continuous SAV file monitoring."""

import asyncio
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor

logger = logging.getLogger(__name__)


class SavMonitorWorker(QThread):
    """Worker thread for continuous SAV file monitoring.

    The completion signal is named ``monitor_finished`` (not ``finished``) to
    avoid shadowing ``QThread``'s built-in ``finished`` signal.
    """

    monitor_finished = Signal(bool)  # True = stopped normally, False = error
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

            self._processor = SaveFileProcessor(
                file_path=self._sav_path,
                output_coordinator=self._output_coordinator,
                poll_interval=self._poll_interval,
                emit_all_on_start=False,
            )
            # stop() may have run before the processor existed.
            if self._should_stop:
                self._processor.stop()

            asyncio.run(self._run_monitor())

            logger.info("Monitor stopped")
            self.monitor_finished.emit(True)

        except RuntimeError as e:
            self.error.emit(str(e))
            self.monitor_finished.emit(False)
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            self.error.emit(f"Error monitoring SAV file: {e}")
            self.monitor_finished.emit(False)

    async def _run_monitor(self) -> None:
        """Run the monitoring loop with change detection callback."""
        processor = self._processor
        if processor is None:
            return

        def on_changed(changed: list[Stockpile]) -> None:
            self.stockpiles_changed.emit(changed)
            self.output_response.emit(processor.last_output)

        count = await processor.prime()
        if count is not None:
            self.progress.emit(f"Monitoring {count} stockpile(s)...")

        await processor.run(on_changed=on_changed)
