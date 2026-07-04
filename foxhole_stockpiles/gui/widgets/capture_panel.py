"""Capture control panel: screenshot capture + local scanning, plus SAV tools.

Replaces the former server control panel. Instead of starting a REST server, the
panel runs the OCR engine in-process: a global hotkey (or the *Scan a file* menu
action) captures the Foxhole window, scans it locally, and routes the result to
the configured output handlers.
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.utils import auto_detect_savefile
from foxhole_stockpiles.enums.clip_mode import ClipMode
from foxhole_stockpiles.enums.sav_mode import SavMode
from foxhole_stockpiles.gui.utils.capture_availability import (
    catalog_available,
    sav_file_available,
)
from foxhole_stockpiles.gui.utils.capture_feed_formatting import ocr_summary, stockpile_summary
from foxhole_stockpiles.gui.utils.capture_scan_worker import LocalScanWorker
from foxhole_stockpiles.gui.utils.clipboard_workers import (
    ClipboardMonitorWorker,
    ClipboardScanWorker,
)
from foxhole_stockpiles.gui.utils.hotkey_listener import HotkeyListener, global_hotkeys_supported
from foxhole_stockpiles.gui.utils.sav_workers import SavMonitorWorker, SavScanWorker
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.clipboard_scan import (
    ClipboardScanService,
    build_clipboard_scan_service,
)
from foxhole_stockpiles.services.local_scan import LocalScanService
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator

logger = logging.getLogger(__name__)


class CapturePanel(QWidget):
    """Panel for capturing screenshots, scanning them locally, and SAV tools."""

    capture_triggered = Signal()
    sav_capture_triggered = Signal()
    clip_capture_triggered = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the capture control panel.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.capturing = False
        self._scan_service: LocalScanService | None = None
        self._capture_busy = False
        self._scan_workers: list[LocalScanWorker] = []
        # One listener dispatches every configured hotkey method (OCR / manual
        # SAV / manual clipboard) — a single OS keyboard hook, not one per method.
        self._hotkey_listener: HotkeyListener | None = None
        # Global hotkeys don't work in every environment (e.g. WSL); when
        # unavailable, the hotkey-driven methods are disabled.
        self._hotkeys_available = global_hotkeys_supported()

        # SAV processing state
        self._sav_mode: SavMode = SavMode.MANUAL
        self._sav_scan_worker: SavScanWorker | None = None
        self._sav_listening = False
        self._sav_monitor_worker: SavMonitorWorker | None = None
        self._sav_monitoring = False

        # Clipboard processing state
        self._clip_mode: ClipMode = ClipMode.MANUAL
        self._clip_service: ClipboardScanService | None = None
        self._clip_scan_worker: ClipboardScanWorker | None = None
        self._clip_listening = False
        self._clip_monitor_worker: ClipboardMonitorWorker | None = None
        self._clip_monitoring = False

        # Tracks whether the "no method configured" hint has been shown so it is
        # not repeated on every settings refresh while still unconfigured.
        self._get_started_shown = False

        self.init_ui()

        if not self._hotkeys_available:
            logger.warning(
                "Global hotkeys are unavailable in this environment (e.g. WSL); "
                "screenshot and manual-SAV capture are disabled. Use the Windows "
                "build for hotkeys, or the File menu / SAV monitor mode instead."
            )

        # Run the capture-and-scan on the GUI thread when a hotkey fires.
        self.capture_triggered.connect(self._on_capture_triggered)
        self.sav_capture_triggered.connect(self._on_sav_capture_triggered)
        self.clip_capture_triggered.connect(self._on_clip_capture_triggered)

        # Connect to language changes with cleanup on destruction
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(self._cleanup)

        # On first run nothing is configured yet; point the user at Settings.
        self._maybe_prompt_setup()

    def _cleanup(self) -> None:
        """Clean up resources when widget is destroyed."""
        off_language_changed(self._language_callback)
        self._stop_all_workers()

    def _stop_all_workers(self) -> None:
        """Stop the hotkey listener and all SAV/clipboard workers; wait for them."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        self.capturing = False
        self._sav_listening = False
        self._clip_listening = False

        for worker in list(self._scan_workers):
            if worker.isRunning():
                worker.wait(2000)

        if self._sav_monitor_worker and self._sav_monitor_worker.isRunning():
            self._sav_monitor_worker.stop()
            self._sav_monitor_worker.wait(2000)

        if self._sav_scan_worker and self._sav_scan_worker.isRunning():
            self._sav_scan_worker.wait(2000)

        if self._clip_monitor_worker and self._clip_monitor_worker.isRunning():
            self._clip_monitor_worker.stop()
            self._clip_monitor_worker.wait(2000)

        if self._clip_scan_worker and self._clip_scan_worker.isRunning():
            self._clip_scan_worker.wait(2000)

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event.

        Args:
            _language: The new language code (unused).
        """
        self.retranslate()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Top section: a single control that enables/disables every configured
        # input method at once, plus one read-only status group per method
        # (OCR / SAV / Clipboard) showing its key, "monitoring", or that it is
        # not configured.
        top_layout = QHBoxLayout()
        top_layout.addWidget(self._build_controls_group(), 1)
        top_layout.addWidget(self._build_capture_group(), 1)
        top_layout.addWidget(self._build_sav_group(), 1)
        top_layout.addWidget(self._build_clip_group(), 1)
        layout.addLayout(top_layout)

        layout.addWidget(self._build_logs_group(), 1)

        self.retranslate()
        self._apply_sav_mode()
        self._apply_clip_mode()

    def _build_controls_group(self) -> QGroupBox:
        """Build the single button that governs all configured methods.

        Returns:
            QGroupBox: The controls group box.
        """
        self.controls_group = QGroupBox("")
        self.controls_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        controls_layout = QVBoxLayout(self.controls_group)
        self.start_stop_button = QPushButton("")
        self.start_stop_button.clicked.connect(self.toggle_all)
        controls_layout.addWidget(self.start_stop_button)
        return self.controls_group

    def _build_capture_group(self) -> QGroupBox:
        """Build the OCR (screenshot) status group.

        Returns:
            QGroupBox: The capture status group box.
        """
        self.capture_group = QGroupBox("")
        self.capture_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        capture_layout = QVBoxLayout(self.capture_group)
        self.ocr_status = QLabel("")
        capture_layout.addWidget(self.ocr_status)
        return self.capture_group

    def _build_sav_group(self) -> QGroupBox:
        """Build the SAV status group.

        Returns:
            QGroupBox: The SAV status group box.
        """
        self.sav_group = QGroupBox("")
        self.sav_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sav_layout = QVBoxLayout(self.sav_group)
        self.sav_status = QLabel("")
        sav_layout.addWidget(self.sav_status)
        return self.sav_group

    def _build_clip_group(self) -> QGroupBox:
        """Build the clipboard status group.

        Returns:
            QGroupBox: The clipboard status group box.
        """
        self.clip_group = QGroupBox("")
        self.clip_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        clip_layout = QVBoxLayout(self.clip_group)
        self.clip_status = QLabel("")
        clip_layout.addWidget(self.clip_status)
        return self.clip_group

    def _build_logs_group(self) -> QGroupBox:
        """Build the activity feed group.

        A plain, read-only text view of friendly, user-facing messages — not
        the technical log, which still flows through `logging` to wherever
        the user configured it. Always shown; fills the space under the
        fixed-height status groups.

        Returns:
            QGroupBox: The activity feed group box.
        """
        self.logs_group = QGroupBox("")
        logs_layout = QVBoxLayout()
        self.logs_group.setLayout(logs_layout)

        self.activity_feed = QPlainTextEdit()
        self.activity_feed.setReadOnly(True)
        # Cap the buffer so a long-running session does not grow unbounded.
        self.activity_feed.setMaximumBlockCount(1000)
        self.activity_feed.setStyleSheet(
            "QPlainTextEdit { background-color: #1E1E1E; color: #DDDDDD; }"
        )
        logs_layout.addWidget(self.activity_feed)

        log_controls = QHBoxLayout()
        self.clear_logs_button = QPushButton("")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        log_controls.addStretch()
        log_controls.addWidget(self.clear_logs_button)
        logs_layout.addLayout(log_controls)

        return self.logs_group

    def refresh_db_info(self) -> None:
        """Re-read settings and refresh button availability (rebuilds the scanner)."""
        # Settings may have changed; drop the cached services so they rebuild.
        self._scan_service = None
        self._clip_service = None
        self._apply_sav_mode()
        self._apply_clip_mode()
        self._maybe_prompt_setup()

    def _is_active(self) -> bool:
        """Return whether any input method is currently running.

        Returns:
            bool: True if a hotkey listener or monitor is active.
        """
        return (
            self.capturing
            or self._sav_listening
            or self._sav_monitoring
            or self._clip_listening
            or self._clip_monitoring
        )

    def _ocr_status_text(self, settings: AppSettings) -> str:
        """Return the OCR (screenshot) status: its key, unavailable, or unset.

        Args:
            settings (AppSettings): The settings to read the OCR config from.

        Returns:
            str: The hotkey, an "unavailable" notice, or "not configured".
        """
        db_path = settings.scanner.database_path
        db_valid = db_path is not None and db_path.exists()
        if db_valid and settings.scanner.capture_key:
            if self._hotkeys_available:
                return settings.scanner.capture_key
            return t("server_panel.status_unavailable")
        return t("server_panel.status_not_configured")

    def _sav_status_text(self, settings: AppSettings) -> str:
        """Return the SAV status: "monitoring", its key, unavailable, or unset.

        Args:
            settings (AppSettings): The settings to read the SAV config from.

        Returns:
            str: The configured-state descriptor for the SAV method.
        """
        if self._sav_mode == SavMode.MONITOR:
            if sav_file_available(settings):
                return t("server_panel.status_monitoring")
            return t("server_panel.status_not_configured")
        key = settings.sav_processing.sav_capture_key
        if key:
            return key if self._hotkeys_available else t("server_panel.status_unavailable")
        return t("server_panel.status_not_configured")

    def _clip_status_text(self, settings: AppSettings) -> str:
        """Return the clipboard status: "monitoring", its key, unavailable, or unset.

        Args:
            settings (AppSettings): The settings to read the clipboard config from.

        Returns:
            str: The configured-state descriptor for the clipboard method.
        """
        if not catalog_available(settings):
            return t("server_panel.status_not_configured")
        if self._clip_mode == ClipMode.MONITOR:
            return t("server_panel.status_monitoring")
        key = settings.clipboard.clip_capture_key
        if key:
            return key if self._hotkeys_available else t("server_panel.status_unavailable")
        return t("server_panel.status_not_configured")

    def _refresh_controls(self) -> None:
        """Refresh the per-method status labels and the single Start/Stop button.

        The button is labelled for its next action (start vs stop) and enabled
        when at least one method is usable or something is already running.
        """
        try:
            settings: AppSettings | None = AppSettings()
        except Exception:  # noqa: BLE001 - keep the UI responsive if settings fail
            settings = None

        if settings is not None:
            self.ocr_status.setText(self._ocr_status_text(settings))
            self.sav_status.setText(self._sav_status_text(settings))
            self.clip_status.setText(self._clip_status_text(settings))
            any_usable = self._any_method_usable(settings)
        else:
            unset = t("server_panel.status_not_configured")
            self.ocr_status.setText(unset)
            self.sav_status.setText(unset)
            self.clip_status.setText(unset)
            any_usable = False

        active = self._is_active()
        self.start_stop_button.setText(
            t("server_panel.stop_all") if active else t("server_panel.start_all")
        )
        self.start_stop_button.setEnabled(any_usable or active)

    def toggle_all(self) -> None:
        """Enable or disable every configured input method with one action."""
        if self._is_active():
            self._stop_all()
        else:
            self._start_all()

    def _collect_bindings(
        self, settings: AppSettings
    ) -> tuple[dict[str, Callable[[], None]], list[tuple[str, str]]]:
        """Collect hotkey bindings for every configured key-driven method.

        Args:
            settings (AppSettings): The current app settings.

        Returns:
            tuple[dict[str, Callable[[], None]], list[tuple[str, str]]]: The
                hotkey-to-callback bindings for a single `HotkeyListener`, and
                the matching (kind, key) pairs to announce once it starts.
        """
        bindings: dict[str, Callable[[], None]] = {}
        announce: list[tuple[str, str]] = []

        db_path = settings.scanner.database_path
        db_valid = db_path is not None and db_path.exists()
        if db_valid and settings.scanner.capture_key and self._hotkeys_available:
            bindings[settings.scanner.capture_key] = self.capture_triggered.emit
            announce.append(("ocr", settings.scanner.capture_key))

        if (
            self._sav_mode == SavMode.MANUAL
            and settings.sav_processing.sav_capture_key
            and self._hotkeys_available
        ):
            bindings[settings.sav_processing.sav_capture_key] = self.sav_capture_triggered.emit
            announce.append(("sav", settings.sav_processing.sav_capture_key))

        if (
            self._clip_mode == ClipMode.MANUAL
            and catalog_available(settings)
            and settings.clipboard.clip_capture_key
            and self._hotkeys_available
        ):
            bindings[settings.clipboard.clip_capture_key] = self.clip_capture_triggered.emit
            announce.append(("clip", settings.clipboard.clip_capture_key))

        return bindings, announce

    def _announce_armed(self, kind: str, key: str) -> None:
        """Mark a key-driven method as armed and log/feed its start.

        Args:
            kind (str): Which method armed — "ocr", "sav", or "clip".
            key (str): The hotkey bound to it.
        """
        if kind == "ocr":
            self.capturing = True
            logger.info("Capture armed (hotkey: %s)", key)
            self._feed(t("activity.capture_started", hotkey=key))
        elif kind == "sav":
            self._sav_listening = True
            logger.info("SAV hotkey armed (hotkey: %s)", key)
            self._feed(t("activity.sav_capture_started", hotkey=key))
        else:
            self._clip_listening = True
            logger.info("Clipboard hotkey armed (hotkey: %s)", key)
            self._feed(t("activity.clip_capture_started", hotkey=key))

    def _start_all(self) -> None:
        """Arm one hotkey listener for all key methods, then start any monitors."""
        try:
            settings = AppSettings()
        except Exception as e:  # noqa: BLE001 - surface config errors in the log
            logger.error("Cannot read settings to start capture: %s", e)
            return

        # Collect the bindings for every configured key-driven method into one
        # listener (a single OS hook), noting what to announce once it starts.
        bindings, announce = self._collect_bindings(settings)

        if bindings:
            try:
                self._hotkey_listener = HotkeyListener(bindings)
                self._hotkey_listener.start()
            except (RuntimeError, ValueError) as e:
                logger.error("Could not start hotkey listener: %s", e)
                self._hotkey_listener = None
                announce = []

        for kind, key in announce:
            self._announce_armed(kind, key)

        # Monitors are independent pollers, not hotkey listeners.
        if self._sav_mode == SavMode.MONITOR and sav_file_available(settings):
            self.start_sav_monitor()
        if self._clip_mode == ClipMode.MONITOR and catalog_available(settings):
            self.start_clip_monitor()

        self._refresh_controls()

    def _stop_all(self) -> None:
        """Stop the shared hotkey listener and any running monitors."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

        if self.capturing:
            self.capturing = False
            self._feed(t("activity.capture_stopped"))
        if self._sav_listening:
            self._sav_listening = False
            self._feed(t("activity.sav_capture_stopped"))
        if self._clip_listening:
            self._clip_listening = False
            self._feed(t("activity.clip_capture_stopped"))

        if self._sav_monitoring:
            self.stop_sav_monitor()
        if self._clip_monitoring:
            self.stop_clip_monitor()

        self._refresh_controls()

    @staticmethod
    def _catalog_available(settings: AppSettings) -> bool:
        """Return whether a usable item catalog file is configured.

        Args:
            settings (AppSettings): The settings to read the catalog path from.

        Returns:
            bool: True if a catalog file is configured and exists.
        """
        return catalog_available(settings)

    @staticmethod
    def _sav_file_available(settings: AppSettings) -> bool:
        """Return whether a .sav file is configured-and-exists or auto-detectable.

        Args:
            settings (AppSettings): The settings to read the .sav path from.

        Returns:
            bool: True if a usable .sav file path is available.
        """
        return sav_file_available(settings)

    def _get_scan_service(self) -> LocalScanService | None:
        """Build (once) and return the local scan service.

        Returns:
            LocalScanService | None: The scan service, or None if it could not be
                built (e.g. database missing); an error is logged in that case.
        """
        if self._scan_service is not None:
            return self._scan_service

        try:
            self._scan_service = LocalScanService(AppSettings())
        except Exception as e:  # noqa: BLE001 - surface config/DB errors in the log
            logger.error("Cannot initialize scanner: %s", e)
            return None
        return self._scan_service

    # ==================== Activity feed ====================

    def _feed(self, message: str) -> None:
        """Append a timestamped, user-facing line to the activity feed.

        Args:
            message (str): The friendly message to show.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_feed.appendPlainText(f"[{timestamp}] {message}")

    def _feed_detail(self, message: str) -> None:
        """Append an indented detail line (e.g. one scanned structure).

        Args:
            message (str): The detail line to show, indented under a summary.
        """
        self.activity_feed.appendPlainText(f"    {message}")

    def _on_output_response(self, response: object) -> None:
        """Write the first return/webhook handler's response to the feed.

        Args:
            response (object): The output coordinator's response — a list of
                webhook messages (one line each), a dict (return / sheets)
                rendered as JSON text, or None when nothing was returned.
        """
        if response is None:
            return
        if isinstance(response, list):
            for message in response:
                self._feed(t("activity.output_response", text=str(message)))
        elif isinstance(response, dict):
            text = json.dumps(response, ensure_ascii=False)
            self._feed(t("activity.output_response", text=text))
        else:
            self._feed(t("activity.output_response", text=str(response)))

    def _any_method_usable(self, settings: AppSettings) -> bool:
        """Return whether at least one input method is ready to run.

        Mirrors the per-method readiness checks used for the status labels.

        Args:
            settings (AppSettings): The settings to evaluate.

        Returns:
            bool: True if screenshot, SAV, or clipboard capture can run.
        """
        db_path = settings.scanner.database_path
        db_valid = db_path is not None and db_path.exists()
        capture_ok = db_valid and bool(settings.scanner.capture_key) and self._hotkeys_available

        if self._sav_mode == SavMode.MONITOR:
            sav_ok = sav_file_available(settings)
        else:
            sav_ok = bool(settings.sav_processing.sav_capture_key) and self._hotkeys_available

        catalog_ok = catalog_available(settings)
        if self._clip_mode == ClipMode.MONITOR:
            clip_ok = catalog_ok
        else:
            clip_ok = (
                catalog_ok and bool(settings.clipboard.clip_capture_key) and self._hotkeys_available
            )

        return capture_ok or sav_ok or clip_ok

    def _maybe_prompt_setup(self) -> None:
        """Show a one-time 'no method configured' hint when nothing is usable.

        When the user goes from *nothing configured* to *a method configured*,
        the feed is cleared so the now-stale get-started hint (and any earlier
        "not ready" noise) does not linger and confuse them. Changing settings
        that were already usable leaves the feed untouched.
        """
        try:
            settings = AppSettings()
        except Exception:  # noqa: BLE001 - if settings can't load, stay quiet
            return

        if self._any_method_usable(settings):
            # Only wipe on the unconfigured -> configured transition, i.e. when
            # the get-started hint had been shown. Edits to an already-usable
            # setup keep their activity history.
            if self._get_started_shown:
                self.clear_logs()
                self._get_started_shown = False
            return

        if not self._get_started_shown:
            self._feed(t("activity.get_started"))
            self._get_started_shown = True

    # ==================== Capture ====================

    def _on_capture_triggered(self) -> None:
        """Capture the Foxhole window and scan it (runs on the GUI thread)."""
        if self._capture_busy:
            logger.debug("Capture already in progress; ignoring hotkey")
            return

        service = self._get_scan_service()
        if service is None:
            return

        settings = AppSettings()
        self._capture_busy = True
        worker = LocalScanWorker(
            service,
            capture=True,
            screenshots_folder=settings.scanner.screenshots_folder,
        )
        self._start_scan_worker(worker, mark_capture=True)

    def scan_screenshot_from_menu(self) -> None:
        """Open a file dialog to select and scan a screenshot (called from menu)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            t("server_panel.select_screenshot"),
            "",
            t("common.image_filter"),
        )
        if filepath:
            self.process_screenshot(filepath)

    def process_screenshot(self, filepath: str) -> None:
        """Scan a screenshot file locally.

        Args:
            filepath (str): Path to the screenshot file.
        """
        service = self._get_scan_service()
        if service is None:
            logger.error(t("server_panel.errors.cannot_scan"))
            return

        worker = LocalScanWorker(service, filepath=filepath)
        self._start_scan_worker(worker, mark_capture=False)

    def _start_scan_worker(self, worker: LocalScanWorker, *, mark_capture: bool) -> None:
        """Wire up and start a scan worker, keeping a reference until it finishes.

        Args:
            worker (LocalScanWorker): The worker to start.
            mark_capture (bool): Whether this worker was started by the hotkey
                (so the busy flag is cleared when it finishes).
        """
        worker.scan_finished.connect(self._on_scan_finished)
        worker.output_response.connect(self._on_output_response)
        worker.scan_error.connect(self._on_scan_error)

        def _done() -> None:
            if mark_capture:
                self._capture_busy = False
            if worker in self._scan_workers:
                self._scan_workers.remove(worker)

        worker.scan_finished.connect(lambda _stockpile: _done())
        worker.scan_error.connect(lambda _msg: _done())
        self._scan_workers.append(worker)
        worker.start()

    def _on_scan_finished(self, stockpile: Stockpile) -> None:
        """Log a short summary when a scan completes.

        Args:
            stockpile (Stockpile): The detected stockpile.
        """
        logger.info(
            "Scan complete: %d item(s) detected (%s)",
            len(stockpile.items),
            stockpile.type,
        )
        self._feed(t("activity.ocr_result", line=ocr_summary(stockpile)))

    def _on_scan_error(self, message: str) -> None:
        """Log a scan failure.

        Args:
            message (str): The error message.
        """
        logger.error("Scan failed: %s", message)
        self._feed(t("activity.scan_error", error=message))

    def clear_logs(self) -> None:
        """Clear the activity feed."""
        self.activity_feed.clear()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.controls_group.setTitle(t("server_panel.controls_group_title"))
        self.capture_group.setTitle(t("server_panel.capture_group_title"))
        self.sav_group.setTitle(t("server_panel.sav_group_title"))
        self.clip_group.setTitle(t("server_panel.clip_group_title"))

        # The button label and per-method status strings are translatable.
        self._refresh_controls()

        self.activity_feed.setPlaceholderText(t("activity.feed_placeholder"))
        self.clear_logs_button.setText(t("common.clear_logs"))

    # ==================== SAV Processing ====================

    def _validate_sav_config(self) -> tuple[Path | None, str | None]:
        """Validate SAV processing configuration.

        Returns:
            tuple: (sav_path, error_message). If error_message is not None, the
                sav_path is invalid.
        """
        try:
            settings = AppSettings()
        except Exception as e:  # noqa: BLE001 - surface config errors to the user
            return None, t("server_panel.sav.error_loading_settings", error=str(e))

        sav_path = settings.sav_processing.sav_file_path
        if not sav_path:
            sav_path = auto_detect_savefile()

        if not sav_path:
            return None, t("server_panel.sav.error_no_sav_file")

        if not sav_path.exists():
            return None, t("server_panel.sav.error_sav_not_found")

        return sav_path, None

    def scan_sav_from_menu(self) -> None:
        """Scan the configured .sav file once (called from the File menu)."""
        sav_path, error = self._validate_sav_config()
        if error:
            QMessageBox.warning(self, t("server_panel.sav.error_title"), error)
            return
        self._run_sav_scan(sav_path)

    def _on_sav_capture_triggered(self) -> None:
        """Scan the .sav file once when the SAV hotkey is pressed (GUI thread)."""
        sav_path, error = self._validate_sav_config()
        if error:
            logger.error("[SAV] %s", error)
            return
        self._run_sav_scan(sav_path)

    def _run_sav_scan(self, sav_path: Path | None) -> None:
        """Start a one-shot SAV scan worker for the given path.

        Args:
            sav_path (Path | None): Validated path to the .sav file to scan.
        """
        if self._sav_scan_worker and self._sav_scan_worker.isRunning():
            logger.warning("SAV scan already in progress")
            return

        try:
            settings = AppSettings()
            output_coordinator = OutputCoordinator(settings.output)
        except Exception as e:  # noqa: BLE001 - surface config/output errors in the log
            logger.error("[SAV] %s", t("server_panel.sav.error_output", error=str(e)))
            return

        assert sav_path is not None

        logger.info("Starting SAV scan: %s", sav_path)
        self._sav_scan_worker = SavScanWorker(sav_path, output_coordinator)
        self._sav_scan_worker.error.connect(self._on_sav_error)
        self._sav_scan_worker.stockpiles_found.connect(self._on_sav_stockpiles)
        self._sav_scan_worker.output_response.connect(self._on_output_response)
        self._sav_scan_worker.finished.connect(self._on_sav_scan_finished)
        self._sav_scan_worker.start()

    def _apply_sav_mode(self) -> None:
        """Read the configured SAV mode and reconfigure the SAV control.

        Switching mode stops any active listening/monitoring so the control
        never has two SAV pipelines running at once.
        """
        try:
            mode = AppSettings().sav_processing.mode
        except Exception as e:  # noqa: BLE001 - default to manual if settings fail to load
            logger.warning("Could not read SAV mode: %s", e)
            mode = SavMode.MANUAL

        if mode != self._sav_mode:
            # Stop everything before switching so no stale pipeline lingers.
            if self._is_active():
                self._stop_all()
            self._sav_mode = mode

        self._refresh_controls()

    def toggle_sav_monitor(self) -> None:
        """Toggle SAV file monitoring on/off (monitor mode)."""
        if self._sav_monitoring:
            self.stop_sav_monitor()
        else:
            self.start_sav_monitor()

    def start_sav_monitor(self) -> None:
        """Start auto-polling the configured .sav file for changes."""
        if self._sav_monitor_worker and self._sav_monitor_worker.isRunning():
            logger.warning("Cannot start monitor: previous monitor still stopping")
            return

        sav_path, error = self._validate_sav_config()
        if error:
            QMessageBox.warning(self, t("server_panel.sav.error_title"), error)
            return

        try:
            settings = AppSettings()
            output_coordinator = OutputCoordinator(settings.output)
            poll_interval = settings.sav_processing.poll_interval
        except Exception as e:  # noqa: BLE001 - surface config/output errors to the user
            QMessageBox.critical(
                self,
                t("server_panel.sav.error_title"),
                t("server_panel.sav.error_output", error=str(e)),
            )
            return

        assert sav_path is not None

        logger.info("Starting SAV monitor: %s (poll: %ss)", sav_path, poll_interval)
        self._sav_monitoring = True
        self._refresh_controls()
        self._feed(t("activity.sav_monitor_started"))

        self._sav_monitor_worker = SavMonitorWorker(sav_path, output_coordinator, poll_interval)
        self._sav_monitor_worker.error.connect(self._on_sav_error)
        self._sav_monitor_worker.stockpiles_changed.connect(self._on_sav_stockpiles)
        self._sav_monitor_worker.output_response.connect(self._on_output_response)
        self._sav_monitor_worker.finished.connect(self._on_sav_monitor_finished)
        self._sav_monitor_worker.start()

    def stop_sav_monitor(self) -> None:
        """Stop auto-polling the .sav file."""
        if self._sav_monitor_worker:
            logger.info("Stopping SAV monitor...")
            self._sav_monitor_worker.stop()

        self._sav_monitoring = False
        self._refresh_controls()
        self._feed(t("activity.sav_monitor_stopped"))

    def _on_sav_monitor_finished(self, success: bool) -> None:
        """Handle the SAV monitor worker finishing.

        Args:
            success (bool): Whether the monitor stopped normally.
        """
        if self.sender() is self._sav_monitor_worker:
            self._sav_monitoring = False
            self._refresh_controls()
            self._sav_monitor_worker = None

    def _on_sav_error(self, error_msg: str) -> None:
        """Handle SAV processing error.

        Args:
            error_msg (str): Error message.
        """
        logger.error("[SAV] %s", error_msg)
        self._feed(t("activity.sav_error", error=error_msg))

    def _on_sav_stockpiles(self, stockpiles: list[Stockpile]) -> None:
        """Show a SAV scan summary plus one feed line per scanned structure.

        Args:
            stockpiles (list[Stockpile]): The structures scanned (or changed).
        """
        if not stockpiles:
            return
        self._feed(t("activity.sav_summary", count=len(stockpiles)))
        for stockpile in stockpiles:
            self._feed_detail(stockpile_summary(stockpile))

    def _on_sav_scan_finished(self, success: bool) -> None:
        """Handle SAV scan finished.

        Args:
            success (bool): Whether scan completed successfully.
        """
        self._sav_scan_worker = None

    # ==================== Clipboard Processing ====================

    def _get_clip_service(self) -> ClipboardScanService | None:
        """Build (once) and return the clipboard scan service.

        Returns:
            ClipboardScanService | None: The service, or None if it could not be
                built (e.g. catalog missing); an error is logged in that case.
        """
        if self._clip_service is not None:
            return self._clip_service

        try:
            self._clip_service = build_clipboard_scan_service(AppSettings())
        except Exception as e:  # noqa: BLE001 - surface config/catalog errors in the log
            logger.error("Cannot initialize clipboard scanner: %s", e)
            return None
        return self._clip_service

    def _apply_clip_mode(self) -> None:
        """Read the configured clipboard mode and reconfigure the control.

        Switching mode stops any active listening/monitoring so the control
        never has two clipboard pipelines running at once.
        """
        try:
            mode = AppSettings().clipboard.mode
        except Exception as e:  # noqa: BLE001 - default to manual if settings fail to load
            logger.warning("Could not read clipboard mode: %s", e)
            mode = ClipMode.MANUAL

        if mode != self._clip_mode:
            # Stop everything before switching so no stale pipeline lingers.
            if self._is_active():
                self._stop_all()
            self._clip_mode = mode

        self._refresh_controls()

    def _on_clip_capture_triggered(self) -> None:
        """Read and scan the clipboard once when the hotkey fires (GUI thread)."""
        if self._clip_scan_worker and self._clip_scan_worker.isRunning():
            logger.debug("Clipboard scan already in progress; ignoring hotkey")
            return

        service = self._get_clip_service()
        if service is None:
            return

        worker = ClipboardScanWorker(service)
        worker.stockpile_found.connect(self._on_clip_stockpile_found)
        worker.output_response.connect(self._on_output_response)
        worker.error.connect(self._on_clip_error)
        worker.finished.connect(lambda _success: self._on_clip_scan_finished())
        self._clip_scan_worker = worker
        worker.start()

    def toggle_clip_monitor(self) -> None:
        """Toggle clipboard monitoring on/off (monitor mode)."""
        if self._clip_monitoring:
            self.stop_clip_monitor()
        else:
            self.start_clip_monitor()

    def start_clip_monitor(self) -> None:
        """Start auto-polling the clipboard for new stockpile exports."""
        if self._clip_monitor_worker and self._clip_monitor_worker.isRunning():
            logger.warning("Cannot start monitor: previous clipboard monitor still stopping")
            return

        service = self._get_clip_service()
        if service is None:
            QMessageBox.warning(
                self,
                t("server_panel.clip.error_title"),
                t("server_panel.clip.error_no_catalog"),
            )
            return

        try:
            poll_interval = AppSettings().clipboard.poll_interval
        except Exception as e:  # noqa: BLE001 - surface config errors to the user
            QMessageBox.critical(self, t("server_panel.clip.error_title"), str(e))
            return

        # Treat whatever is already on the clipboard as "seen" so only a new
        # export triggers an emit.
        service.prime()

        logger.info("Starting clipboard monitor (poll: %ss)", poll_interval)
        self._clip_monitoring = True
        self._refresh_controls()
        self._feed(t("activity.clip_monitor_started"))

        self._clip_monitor_worker = ClipboardMonitorWorker(service, poll_interval)
        self._clip_monitor_worker.error.connect(self._on_clip_error)
        self._clip_monitor_worker.stockpile_found.connect(self._on_clip_stockpile_found)
        self._clip_monitor_worker.output_response.connect(self._on_output_response)
        self._clip_monitor_worker.finished.connect(self._on_clip_monitor_finished)
        self._clip_monitor_worker.start()

    def stop_clip_monitor(self) -> None:
        """Stop auto-polling the clipboard."""
        if self._clip_monitor_worker:
            logger.info("Stopping clipboard monitor...")
            self._clip_monitor_worker.stop()

        self._clip_monitoring = False
        self._refresh_controls()
        self._feed(t("activity.clip_monitor_stopped"))

    def _on_clip_monitor_finished(self, success: bool) -> None:
        """Handle the clipboard monitor worker finishing.

        Args:
            success (bool): Whether the monitor stopped normally.
        """
        if self.sender() is self._clip_monitor_worker:
            self._clip_monitoring = False
            self._refresh_controls()
            self._clip_monitor_worker = None

    def _on_clip_stockpile_found(self, stockpile: Stockpile | None) -> None:
        """Log a short summary when a clipboard scan yields a stockpile.

        Args:
            stockpile (Stockpile | None): The parsed stockpile, or None if the
                clipboard did not hold a recognized stockpile export.
        """
        if stockpile is None:
            logger.info("No stockpile data found in clipboard")
            self._feed(t("activity.clip_empty"))
            return
        logger.info(
            "Clipboard scan complete: %d item(s) (%s)",
            len(stockpile.items),
            stockpile.type,
        )
        self._feed(t("activity.clip_result", line=stockpile_summary(stockpile)))

    def _on_clip_error(self, error_msg: str) -> None:
        """Handle a clipboard processing error.

        Args:
            error_msg (str): Error message.
        """
        logger.error("[Clipboard] %s", error_msg)
        self._feed(t("activity.clip_error", error=error_msg))

    def _on_clip_scan_finished(self) -> None:
        """Handle a one-shot clipboard scan finishing."""
        self._clip_scan_worker = None
