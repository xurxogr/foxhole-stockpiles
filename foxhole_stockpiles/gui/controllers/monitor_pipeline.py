"""Shared lifecycle of an input method that runs on a hotkey or as a monitor."""

import logging
from enum import StrEnum

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from foxhole_stockpiles.gui.controllers.pipeline_host import PipelineHost
from foxhole_stockpiles.gui.utils.clipboard_monitor_worker import ClipboardMonitorWorker
from foxhole_stockpiles.gui.utils.clipboard_scan_worker import ClipboardScanWorker
from foxhole_stockpiles.gui.utils.sav_monitor_worker import SavMonitorWorker
from foxhole_stockpiles.gui.utils.sav_scan_worker import SavScanWorker
from foxhole_stockpiles.i18n import t

logger = logging.getLogger(__name__)

WORKER_WAIT_MS = 2000


class MonitorPipeline(QObject):
    """Run one input method in manual (hotkey) or monitor (polling) mode.

    Subclasses set the class attributes below, read their mode from settings,
    and build their workers.
    """

    _log_tag = ""
    _monitor_name = ""
    _armed_key = ""
    _disarmed_key = ""
    _monitor_started_key = ""
    _monitor_stopped_key = ""
    _error_key = ""

    def __init__(self, host: PipelineHost, parent: QWidget, manual_mode: StrEnum) -> None:
        """Initialize the pipeline in manual mode.

        Args:
            host (PipelineHost): The widget this pipeline reports to.
            parent (QWidget): Owner of this pipeline and parent of its dialogs.
            manual_mode (StrEnum): The mode used until settings say otherwise.
        """
        super().__init__(parent)
        self._host = host
        self._parent = parent
        self._manual_mode = manual_mode
        self.mode = manual_mode
        self.listening = False
        self.monitoring = False
        self._scan_worker: SavScanWorker | ClipboardScanWorker | None = None
        self._monitor_worker: SavMonitorWorker | ClipboardMonitorWorker | None = None

    def _read_mode(self) -> StrEnum:
        """Read the configured mode from settings.

        Returns:
            StrEnum: The configured mode.

        Raises:
            NotImplementedError: If the subclass does not override this.
        """
        raise NotImplementedError

    def start_monitor(self) -> None:
        """Start polling for changes.

        Raises:
            NotImplementedError: If the subclass does not override this.
        """
        raise NotImplementedError

    def apply_mode(self) -> None:
        """Read the configured mode and reconfigure the method.

        Switching mode stops any active listening/monitoring so the method never
        has two pipelines running at once.
        """
        try:
            mode = self._read_mode()
        except Exception as e:  # noqa: BLE001 - default to manual if settings fail to load
            logger.warning("Could not read %s mode: %s", self._monitor_name, e)
            mode = self._manual_mode

        if mode != self.mode:
            if self._host.is_active():
                self._host.stop_all()
            self.mode = mode

        self._host.refresh_controls()

    def arm(self, key: str) -> None:
        """Mark the hotkey as armed and report it.

        Args:
            key (str): The hotkey bound to this method.
        """
        self.listening = True
        logger.info("%s hotkey armed (hotkey: %s)", self._log_tag, key)
        self._host.feed(t(self._armed_key, hotkey=key))

    def disarm(self) -> None:
        """Mark the hotkey as no longer armed and report it, if it was armed."""
        if self.listening:
            self.listening = False
            self._host.feed(t(self._disarmed_key))

    def toggle_monitor(self) -> None:
        """Toggle monitoring on/off (monitor mode)."""
        if self.monitoring:
            self.stop_monitor()
        else:
            self.start_monitor()

    def stop_monitor(self) -> None:
        """Stop polling for changes."""
        if self._monitor_worker:
            logger.info("Stopping %s monitor...", self._monitor_name)
            self._monitor_worker.stop()

        self.monitoring = False
        self._host.refresh_controls()
        self._host.feed(t(self._monitor_stopped_key))

    def shutdown(self) -> None:
        """Stop the workers and wait for them."""
        self.listening = False

        if self._monitor_worker and self._monitor_worker.isRunning():
            self._monitor_worker.stop()
            self._monitor_worker.wait(WORKER_WAIT_MS)

        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.wait(WORKER_WAIT_MS)

    def _scan_running(self) -> bool:
        """Return whether a one-shot scan is in progress.

        Returns:
            bool: True if a scan worker is running.
        """
        return self._scan_worker is not None and self._scan_worker.isRunning()

    def _monitor_running(self) -> bool:
        """Return whether a monitor thread is still alive.

        Returns:
            bool: True if a monitor worker is running.
        """
        return self._monitor_worker is not None and self._monitor_worker.isRunning()

    def _mark_monitoring(self) -> None:
        """Flag the monitor as running and report it."""
        self.monitoring = True
        self._host.refresh_controls()
        self._host.feed(t(self._monitor_started_key))

    def _launch_scan(self, worker: SavScanWorker | ClipboardScanWorker) -> None:
        """Connect the signals every scan worker shares and start it.

        Args:
            worker (SavScanWorker | ClipboardScanWorker): The worker to start.
        """
        self._scan_worker = worker
        worker.error.connect(self._on_error)
        worker.output_response.connect(self._host.on_output_response)
        worker.scan_finished.connect(self._on_scan_finished)
        worker.start()

    def _launch_monitor(self, worker: SavMonitorWorker | ClipboardMonitorWorker) -> None:
        """Connect the signals every monitor worker shares and start it.

        Args:
            worker (SavMonitorWorker | ClipboardMonitorWorker): The worker to start.
        """
        self._monitor_worker = worker
        worker.error.connect(self._on_error)
        worker.output_response.connect(self._host.on_output_response)
        worker.monitor_finished.connect(self._on_monitor_finished)
        worker.start()

    def _on_scan_finished(self, _success: bool) -> None:
        """Forget the one-shot scan worker once it finished.

        Args:
            _success (bool): Whether the scan completed successfully (unused).
        """
        self._scan_worker = None

    def _on_monitor_finished(self, _success: bool) -> None:
        """Handle the monitor worker finishing.

        Args:
            _success (bool): Whether the monitor stopped normally (unused).
        """
        if self.sender() is self._monitor_worker:
            self.monitoring = False
            self._host.refresh_controls()
            self._monitor_worker = None

    def _on_error(self, error_msg: str) -> None:
        """Log and report a processing error.

        Args:
            error_msg (str): Error message.
        """
        logger.error("[%s] %s", self._log_tag, error_msg)
        self._host.feed(t(self._error_key, error=error_msg))
