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

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.enums.capture_mode import CaptureMode
from foxhole_stockpiles.gui.controllers.clip_pipeline import ClipPipeline
from foxhole_stockpiles.gui.controllers.ocr_pipeline import OcrPipeline
from foxhole_stockpiles.gui.controllers.sav_pipeline import SavPipeline
from foxhole_stockpiles.gui.utils.capture_availability import (
    catalog_available,
    sav_file_available,
)
from foxhole_stockpiles.gui.utils.hotkey_listener import HotkeyListener, global_hotkeys_supported
from foxhole_stockpiles.i18n import on_language_changed, t

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
        # One listener dispatches every configured hotkey method (OCR / manual
        # SAV / manual clipboard) — a single OS keyboard hook, not one per method.
        self._hotkey_listener: HotkeyListener | None = None
        # Global hotkeys only work on Windows with the capture extra; when
        # unavailable, the hotkey-driven methods are disabled.
        self._hotkeys_available = global_hotkeys_supported()

        self.ocr_pipeline = OcrPipeline(host=self, parent=self)
        self.sav_pipeline = SavPipeline(host=self, parent=self)
        self.clip_pipeline = ClipPipeline(host=self, parent=self)

        # Tracks whether the "no method configured" hint has been shown so it is
        # not repeated on every settings refresh while still unconfigured.
        self._get_started_shown = False

        self.init_ui()

        if not self._hotkeys_available:
            logger.warning(
                "Global hotkeys require Windows with the 'capture' extra installed; "
                "screenshot and manual-SAV capture are disabled. Use the Windows "
                "build for hotkeys, or the File menu / SAV monitor mode instead."
            )

        # Run the capture-and-scan on the GUI thread when a hotkey fires.
        self.capture_triggered.connect(self.ocr_pipeline.on_capture_triggered)
        self.sav_capture_triggered.connect(self.sav_pipeline.on_capture_triggered)
        self.clip_capture_triggered.connect(self.clip_pipeline.on_capture_triggered)

        # Connect to language changes with cleanup on destruction
        on_language_changed(self._on_language_changed)

        # On first run nothing is configured yet; point the user at Settings.
        self._maybe_prompt_setup()

    def _stop_all_workers(self) -> None:
        """Stop the hotkey listener and all SAV/clipboard workers; wait for them."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        self.capturing = False

        self.ocr_pipeline.shutdown()
        self.sav_pipeline.shutdown()
        self.clip_pipeline.shutdown()

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
        self.capture_group, self.ocr_status = self._build_status_group()
        self.sav_group, self.sav_status = self._build_status_group()
        self.clip_group, self.clip_status = self._build_status_group()
        top_layout.addWidget(self.capture_group, 1)
        top_layout.addWidget(self.sav_group, 1)
        top_layout.addWidget(self.clip_group, 1)
        layout.addLayout(top_layout)

        layout.addWidget(self._build_logs_group(), 1)

        self.retranslate()
        self.sav_pipeline.apply_mode()
        self.clip_pipeline.apply_mode()

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

    @staticmethod
    def _build_status_group() -> tuple[QGroupBox, QLabel]:
        """Build the group showing the status of one capture method.

        Returns:
            tuple[QGroupBox, QLabel]: The group box and its status label.
        """
        group = QGroupBox("")
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        status = QLabel("")
        QVBoxLayout(group).addWidget(status)
        return group, status

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
        self.ocr_pipeline.reset_service()
        self.clip_pipeline.reset_service()
        self.sav_pipeline.apply_mode()
        self.clip_pipeline.apply_mode()
        self._maybe_prompt_setup()

    def is_active(self) -> bool:
        """Return whether any input method is currently running.

        Returns:
            bool: True if a hotkey listener or monitor is active.
        """
        return (
            self.capturing
            or self.sav_pipeline.listening
            or self.sav_pipeline.monitoring
            or self.clip_pipeline.listening
            or self.clip_pipeline.monitoring
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
        if self.sav_pipeline.mode == CaptureMode.MONITOR:
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
        if self.clip_pipeline.mode == CaptureMode.MONITOR:
            return t("server_panel.status_monitoring")
        key = settings.clipboard.clip_capture_key
        if key:
            return key if self._hotkeys_available else t("server_panel.status_unavailable")
        return t("server_panel.status_not_configured")

    def refresh_controls(self) -> None:
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

        active = self.is_active()
        self.start_stop_button.setText(
            t("server_panel.stop_all") if active else t("server_panel.start_all")
        )
        self.start_stop_button.setEnabled(any_usable or active)

    def toggle_all(self) -> None:
        """Enable or disable every configured input method with one action."""
        if self.is_active():
            self.stop_all()
        else:
            self._start_all()

    def _collect_bindings(
        self, settings: AppSettings
    ) -> tuple[dict[str, Callable[[], None]], list[tuple[Callable[[str], None], str]]]:
        """Collect hotkey bindings for every configured key-driven method.

        Args:
            settings (AppSettings): The current app settings.

        Returns:
            tuple[dict[str, Callable[[], None]], list[tuple[Callable[[str], None], str]]]:
                The hotkey-to-callback bindings for a single `HotkeyListener`, and
                the matching (arm callback, key) pairs to call once it starts.
        """
        bindings: dict[str, Callable[[], None]] = {}
        announce: list[tuple[Callable[[str], None], str]] = []

        db_path = settings.scanner.database_path
        db_valid = db_path is not None and db_path.exists()
        if db_valid and settings.scanner.capture_key and self._hotkeys_available:
            bindings[settings.scanner.capture_key] = self.capture_triggered.emit
            announce.append((self._arm_capture, settings.scanner.capture_key))

        if (
            self.sav_pipeline.mode == CaptureMode.MANUAL
            and settings.sav_processing.sav_capture_key
            and self._hotkeys_available
        ):
            bindings[settings.sav_processing.sav_capture_key] = self.sav_capture_triggered.emit
            announce.append((self.sav_pipeline.arm, settings.sav_processing.sav_capture_key))

        if (
            self.clip_pipeline.mode == CaptureMode.MANUAL
            and catalog_available(settings)
            and settings.clipboard.clip_capture_key
            and self._hotkeys_available
        ):
            bindings[settings.clipboard.clip_capture_key] = self.clip_capture_triggered.emit
            announce.append((self.clip_pipeline.arm, settings.clipboard.clip_capture_key))

        return bindings, announce

    def _arm_capture(self, key: str) -> None:
        """Mark the screenshot hotkey as armed and report it.

        Args:
            key (str): The hotkey bound to the screenshot capture.
        """
        self.capturing = True
        logger.info("Capture armed (hotkey: %s)", key)
        self.feed(t("activity.capture_started", hotkey=key))

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

        for arm, key in announce:
            arm(key)

        # Monitors are independent pollers, not hotkey listeners.
        if self.sav_pipeline.mode == CaptureMode.MONITOR and sav_file_available(settings):
            self.sav_pipeline.start_monitor()
        if self.clip_pipeline.mode == CaptureMode.MONITOR and catalog_available(settings):
            self.clip_pipeline.start_monitor()

        self.refresh_controls()

    def stop_all(self) -> None:
        """Stop the shared hotkey listener and any running monitors."""
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

        if self.capturing:
            self.capturing = False
            self.feed(t("activity.capture_stopped"))
        self.sav_pipeline.disarm()
        self.clip_pipeline.disarm()

        if self.sav_pipeline.monitoring:
            self.sav_pipeline.stop_monitor()
        if self.clip_pipeline.monitoring:
            self.clip_pipeline.stop_monitor()

        self.refresh_controls()

    # ==================== Activity feed ====================

    def feed(self, message: str) -> None:
        """Append a timestamped, user-facing line to the activity feed.

        Args:
            message (str): The friendly message to show.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_feed.appendPlainText(f"[{timestamp}] {message}")

    def feed_detail(self, message: str) -> None:
        """Append an indented detail line (e.g. one scanned structure).

        Args:
            message (str): The detail line to show, indented under a summary.
        """
        self.activity_feed.appendPlainText(f"    {message}")

    def on_output_response(self, response: object) -> None:
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
                self.feed(t("activity.output_response", text=str(message)))
        elif isinstance(response, dict):
            text = json.dumps(response, ensure_ascii=False)
            self.feed(t("activity.output_response", text=text))
        else:
            self.feed(t("activity.output_response", text=str(response)))

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

        if self.sav_pipeline.mode == CaptureMode.MONITOR:
            sav_ok = sav_file_available(settings)
        else:
            sav_ok = bool(settings.sav_processing.sav_capture_key) and self._hotkeys_available

        catalog_ok = catalog_available(settings)
        if self.clip_pipeline.mode == CaptureMode.MONITOR:
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
            self.feed(t("activity.get_started"))
            self._get_started_shown = True

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
        self.refresh_controls()

        self.activity_feed.setPlaceholderText(t("activity.feed_placeholder"))
        self.clear_logs_button.setText(t("common.clear_logs"))
