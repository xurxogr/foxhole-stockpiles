"""Tests for the CapturePanel widget.

Heavy collaborators (modal dialogs, hotkey listeners, Qt worker threads, and the
scan/clipboard services) are patched at the module level so these tests exercise
the panel's own wiring and state machine without spawning threads or blocking on
dialogs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.enums.clip_mode import ClipMode
from foxhole_stockpiles.enums.sav_mode import SavMode
from foxhole_stockpiles.gui.widgets import capture_panel as cp
from foxhole_stockpiles.models.stockpile import Stockpile


def _m(name: str) -> MagicMock:
    """Return a module-level collaborator mocked in by the autouse fixture."""
    return cast(MagicMock, getattr(cp, name))


class FakeScanWorker(QObject):
    """A scan worker with real Qt signals but a no-op thread lifecycle."""

    scan_finished = Signal(object)
    output_response = Signal(object)
    scan_error = Signal(str)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Accept and ignore the real worker's constructor arguments."""
        super().__init__()

    def start(self) -> None:
        """No-op (the test emits signals manually)."""

    def isRunning(self) -> bool:  # noqa: N802 - mirrors QThread API
        """Report not running."""
        return False

    def wait(self, *args: Any) -> bool:
        """No-op wait."""
        return True


_HEAVY = [
    "QMessageBox",
    "QFileDialog",
    "HotkeyListener",
    "LocalScanWorker",
    "SavScanWorker",
    "SavMonitorWorker",
    "ClipboardScanWorker",
    "ClipboardMonitorWorker",
    "LocalScanService",
    "build_clipboard_scan_service",
    "OutputCoordinator",
]


@pytest.fixture(autouse=True)
def _patch_heavy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace dialogs, listeners, workers and services with mocks."""
    for name in _HEAVY:
        monkeypatch.setattr(cp, name, MagicMock())
    monkeypatch.setattr(cp, "global_hotkeys_supported", lambda: True)
    monkeypatch.setattr(cp, "auto_detect_savefile", lambda: None)


@pytest.fixture
def panel(qtbot: Any) -> cp.CapturePanel:
    """Construct a CapturePanel registered with qtbot."""
    widget = cp.CapturePanel()
    qtbot.addWidget(widget)
    return widget


def _configured(tmp_path: Path) -> AppSettings:
    """Build a fully-configured AppSettings backed by real temp files."""
    db = tmp_path / "db.h5"
    db.write_text("x")
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]")
    settings = AppSettings()
    settings.scanner.capture_key = "<ctrl>+s"
    settings.scanner.database_path = db
    settings.sav_processing.sav_capture_key = "<ctrl>+d"
    settings.sav_processing.sav_file_path = db
    settings.clipboard.clip_capture_key = "<ctrl>+v"
    settings.database_builder.catalog_file = catalog
    return settings


def _use_settings(monkeypatch: pytest.MonkeyPatch, settings: AppSettings) -> None:
    """Make every ``AppSettings()`` call inside the panel return ``settings``."""
    monkeypatch.setattr(cp, "AppSettings", lambda *a, **k: settings)


class TestConstruction:
    """Widget construction and basic UI."""

    def test_builds_widgets(self, panel: cp.CapturePanel) -> None:
        """The panel builds its single control button and status labels."""
        assert panel.start_stop_button is not None
        assert panel.ocr_status is not None
        assert panel.sav_status is not None
        assert panel.clip_status is not None
        assert panel.activity_feed is not None

    def test_starts_idle(self, panel: cp.CapturePanel) -> None:
        """The panel starts in an idle state."""
        assert panel.capturing is False
        assert panel._sav_listening is False
        assert panel._clip_monitoring is False

    def test_construction_without_hotkeys(
        self, qtbot: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When global hotkeys are unavailable, the panel flags it and warns."""
        monkeypatch.setattr(cp, "global_hotkeys_supported", lambda: False)
        widget = cp.CapturePanel()
        qtbot.addWidget(widget)
        assert widget._hotkeys_available is False


class TestLogs:
    """Activity feed behavior."""

    def test_feed_appends_line(self, panel: cp.CapturePanel) -> None:
        """_feed appends a timestamped line to the activity feed."""
        panel.clear_logs()
        panel._feed("hello")
        text = panel.activity_feed.toPlainText()
        assert "hello" in text

    def test_clear_logs(self, panel: cp.CapturePanel) -> None:
        """clear_logs empties the activity feed."""
        panel._feed("something")
        panel.clear_logs()
        assert panel.activity_feed.toPlainText() == ""

    def test_retranslate_sets_button_text(self, panel: cp.CapturePanel) -> None:
        """Retranslate populates translatable labels."""
        panel.retranslate()
        assert panel.start_stop_button.text() != ""
        assert panel.clear_logs_button.text() != ""


class TestOutputResponse:
    """Writing the first return/webhook handler response to the feed."""

    def test_none_writes_nothing(self, panel: cp.CapturePanel) -> None:
        """A None response (console/file only) leaves the feed untouched."""
        panel.clear_logs()
        panel._on_output_response(None)
        assert panel.activity_feed.toPlainText() == ""

    def test_webhook_list_writes_each_message(self, panel: cp.CapturePanel) -> None:
        """A webhook list response writes one feed line per message."""
        panel.clear_logs()
        panel._on_output_response(["Row 1 added", "Row 2 failed"])
        text = panel.activity_feed.toPlainText()
        assert "Row 1 added" in text
        assert "Row 2 failed" in text

    def test_return_dict_writes_json(self, panel: cp.CapturePanel) -> None:
        """A return/sheets dict response is written as JSON text."""
        panel.clear_logs()
        panel._on_output_response({"stockpiles": [{"name": "X"}]})
        text = panel.activity_feed.toPlainText()
        assert "stockpiles" in text
        assert '"name": "X"' in text


class TestAvailabilityHelpers:
    """Static settings-availability helpers."""

    def test_catalog_available(self, tmp_path: Path) -> None:
        """A configured, existing catalog reads as available."""
        settings = _configured(tmp_path)
        assert cp.CapturePanel._catalog_available(settings) is True

    def test_catalog_unavailable(self) -> None:
        """No catalog reads as unavailable."""
        assert cp.CapturePanel._catalog_available(AppSettings()) is False

    def test_sav_file_available(self, tmp_path: Path) -> None:
        """A configured, existing .sav reads as available."""
        settings = _configured(tmp_path)
        assert cp.CapturePanel._sav_file_available(settings) is True

    def test_sav_file_unavailable(self) -> None:
        """No .sav path reads as unavailable."""
        assert cp.CapturePanel._sav_file_available(AppSettings()) is False


class TestButtonStatesAndRefresh:
    """Single-button enablement, status labels, and settings refresh."""

    def test_refresh_controls_unconfigured(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With nothing configured, statuses are non-empty and the button is off."""
        _use_settings(monkeypatch, AppSettings())
        panel._refresh_controls()
        assert panel.ocr_status.text() != ""
        # Nothing usable and not running -> the single button is disabled.
        assert panel.start_stop_button.isEnabled() is False

    def test_refresh_controls_configured(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured setup enables the button and shows the OCR key."""
        settings = _configured(tmp_path)
        _use_settings(monkeypatch, settings)
        panel._refresh_controls()
        assert panel.start_stop_button.isEnabled()
        assert panel.ocr_status.text() == settings.scanner.capture_key

    def test_refresh_db_info_resets_services(self, panel: cp.CapturePanel) -> None:
        """refresh_db_info drops cached services."""
        panel._scan_service = MagicMock()
        panel._clip_service = MagicMock()
        panel.refresh_db_info()
        assert panel._scan_service is None
        assert panel._clip_service is None

    def test_refresh_db_info_resets_services(self, panel: cp.CapturePanel) -> None:
        """refresh_db_info drops cached services."""
        panel._scan_service = MagicMock()
        panel._clip_service = MagicMock()
        panel.refresh_db_info()
        assert panel._scan_service is None
        assert panel._clip_service is None


class TestSetupPrompt:
    """The 'no method configured' hint and feed-clearing transition."""

    def test_shows_hint_when_unconfigured(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With nothing usable, the get-started hint is written once."""
        panel.clear_logs()
        panel._get_started_shown = False
        _use_settings(monkeypatch, AppSettings())
        panel._maybe_prompt_setup()
        assert panel._get_started_shown is True
        assert panel.activity_feed.toPlainText() != ""

    def test_clears_feed_on_first_configure(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Going from unconfigured to configured wipes the stale hint."""
        # Simulate the unconfigured state that has shown the hint.
        panel._get_started_shown = True
        panel._feed("old hint")
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._maybe_prompt_setup()
        assert panel.activity_feed.toPlainText() == ""
        assert panel._get_started_shown is False

    def test_keeps_feed_when_already_configured(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Editing an already-usable setup leaves the activity history intact."""
        panel._get_started_shown = False
        panel.clear_logs()
        panel._feed("scan result")
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._maybe_prompt_setup()
        assert "scan result" in panel.activity_feed.toPlainText()


class TestCapture:
    """Screenshot capture flow."""

    def test_toggle_all_unconfigured_noop(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With nothing configured, toggling stays idle and arms nothing."""
        _use_settings(monkeypatch, AppSettings())
        panel.toggle_all()
        assert panel.capturing is False
        assert panel._is_active() is False

    def test_toggle_all_starts_and_stops_capture(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured OCR key is armed and disarmed by the single button."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.toggle_all()
        assert panel.capturing is True
        assert panel._hotkey_listener is not None
        panel.toggle_all()
        assert panel.capturing is False
        assert panel._hotkey_listener is None

    def test_on_capture_triggered_busy_guard(self, panel: cp.CapturePanel) -> None:
        """A busy capture ignores re-entry."""
        panel._capture_busy = True
        panel._on_capture_triggered()
        # Still busy, no worker spawned.
        assert panel._scan_workers == []

    def test_on_capture_triggered_runs(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A hotkey capture builds and starts a scan worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._on_capture_triggered()
        assert panel._capture_busy is True
        assert len(panel._scan_workers) == 1

    def test_process_screenshot(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A file scan builds and starts a worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.process_screenshot("shot.png")
        assert len(panel._scan_workers) == 1

    def test_process_screenshot_no_service(self, panel: cp.CapturePanel) -> None:
        """No scan service skips the worker."""
        _m("LocalScanService").side_effect = RuntimeError("no db")
        panel.process_screenshot("shot.png")
        assert panel._scan_workers == []

    def test_scan_screenshot_from_menu(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The menu action opens a dialog then scans the chosen file."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("QFileDialog").getOpenFileName.return_value = ("shot.png", "")
        panel.scan_screenshot_from_menu()
        assert len(panel._scan_workers) == 1

    def test_scan_handlers(self, panel: cp.CapturePanel) -> None:
        """Scan finished/error handlers run without error."""
        panel._on_scan_finished(Stockpile())
        panel._on_scan_error("boom")


class TestSav:
    """SAV processing flow."""

    def test_validate_no_sav_file(self, panel: cp.CapturePanel) -> None:
        """No configured/auto-detected .sav yields an error."""
        _path, error = panel._validate_sav_config()
        assert error is not None

    def test_validate_success(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured, existing .sav validates."""
        _use_settings(monkeypatch, _configured(tmp_path))
        path, error = panel._validate_sav_config()
        assert error is None
        assert path is not None

    def test_validate_missing_file(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured-but-missing .sav yields an error."""
        settings = AppSettings()
        settings.sav_processing.sav_file_path = tmp_path / "nope.sav"
        _use_settings(monkeypatch, settings)
        _path, error = panel._validate_sav_config()
        assert error is not None

    def test_toggle_all_starts_sav_manual(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts SAV listening in manual mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._sav_mode = SavMode.MANUAL
        panel.toggle_all()
        assert panel._sav_listening is True

    def test_start_and_stop_sav_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Monitor mode starts and stops the monitor worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.start_sav_monitor()
        assert panel._sav_monitoring is True
        panel.stop_sav_monitor()
        assert panel._sav_monitoring is False

    def test_run_sav_scan(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A one-shot SAV scan starts a worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._run_sav_scan(tmp_path / "db.h5")
        assert panel._sav_scan_worker is not None

    def test_scan_sav_from_menu_error(self, panel: cp.CapturePanel) -> None:
        """The menu action warns when no .sav is available."""
        panel.scan_sav_from_menu()
        _m("QMessageBox").warning.assert_called()

    def test_sav_handlers(self, panel: cp.CapturePanel) -> None:
        """SAV callback handlers run without error."""
        panel._on_sav_error("boom")
        panel._on_sav_scan_finished(True)
        panel._on_sav_monitor_finished(True)

    def test_apply_sav_mode_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Applying monitor mode updates the stored mode."""
        settings = _configured(tmp_path)
        settings.sav_processing.mode = SavMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel._apply_sav_mode()
        assert panel._sav_mode == SavMode.MONITOR


class TestClip:
    """Clipboard processing flow."""

    def test_toggle_all_starts_clip_manual(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts clipboard listening in manual mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._clip_mode = ClipMode.MANUAL
        panel.toggle_all()
        assert panel._clip_listening is True

    def test_start_and_stop_clip_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Monitor mode primes the service and runs the monitor worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.start_clip_monitor()
        assert panel._clip_monitoring is True
        panel.stop_clip_monitor()
        assert panel._clip_monitoring is False

    def test_clip_service_failure_returns_none(self, panel: cp.CapturePanel) -> None:
        """A failed service build yields no clip service."""
        _m("build_clipboard_scan_service").side_effect = RuntimeError("no catalog")
        assert panel._get_clip_service() is None

    def test_on_clip_capture_triggered(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A clipboard hotkey starts a one-shot scan worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._on_clip_capture_triggered()
        assert panel._clip_scan_worker is not None

    def test_clip_handlers(self, panel: cp.CapturePanel) -> None:
        """Clipboard callback handlers run without error."""
        panel._on_clip_error("boom")
        panel._on_clip_scan_finished()
        panel._on_clip_monitor_finished(True)
        panel._on_clip_stockpile_found(None)
        panel._on_clip_stockpile_found(Stockpile())

    def test_apply_clip_mode_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Applying monitor mode updates the stored clipboard mode."""
        settings = _configured(tmp_path)
        settings.clipboard.mode = ClipMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel._apply_clip_mode()
        assert panel._clip_mode == ClipMode.MONITOR


class TestEdgeCases:
    """Guard branches, exception paths, and cleanup."""

    def test_stop_all_workers(self, panel: cp.CapturePanel) -> None:
        """All listeners and running workers are stopped/awaited."""
        panel._hotkey_listener = MagicMock()
        panel._sav_hotkey_listener = MagicMock()
        panel._clip_hotkey_listener = MagicMock()
        scan_worker = MagicMock()
        scan_worker.isRunning.return_value = True
        panel._scan_workers = [scan_worker]
        for attr in (
            "_sav_monitor_worker",
            "_sav_scan_worker",
            "_clip_monitor_worker",
            "_clip_scan_worker",
        ):
            worker = MagicMock()
            worker.isRunning.return_value = True
            setattr(panel, attr, worker)

        panel._stop_all_workers()

        assert panel._hotkey_listener is None
        scan_worker.wait.assert_called()
        panel._sav_monitor_worker.stop.assert_called_once()

    def test_toggle_all_listener_error_leaves_idle(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A shared listener that fails to start arms no hotkey method."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("HotkeyListener").side_effect = RuntimeError("no backend")
        panel.toggle_all()
        assert panel.capturing is False
        assert panel._sav_listening is False
        assert panel._clip_listening is False
        assert panel._hotkey_listener is None

    def test_run_sav_scan_already_running(self, panel: cp.CapturePanel) -> None:
        """A SAV scan already in progress is not restarted."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel._sav_scan_worker = worker
        panel._run_sav_scan(Path("x.sav"))
        assert panel._sav_scan_worker is worker

    def test_start_sav_monitor_already_running(self, panel: cp.CapturePanel) -> None:
        """A SAV monitor already running is not restarted."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel._sav_monitor_worker = worker
        panel.start_sav_monitor()
        assert panel._sav_monitoring is False

    def test_clip_capture_triggered_already_running(self, panel: cp.CapturePanel) -> None:
        """A clipboard scan already in progress ignores the hotkey."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel._clip_scan_worker = worker
        panel._on_clip_capture_triggered()
        assert panel._clip_scan_worker is worker

    def test_start_clip_monitor_already_running(self, panel: cp.CapturePanel) -> None:
        """A clipboard monitor already running is not restarted."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel._clip_monitor_worker = worker
        panel.start_clip_monitor()
        assert panel._clip_monitoring is False

    def test_start_sav_monitor_output_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A failed output coordinator aborts the SAV monitor start."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("OutputCoordinator").side_effect = RuntimeError("bad output")
        panel.start_sav_monitor()
        assert panel._sav_monitoring is False

    def test_apply_sav_mode_settings_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings read failure falls back to manual SAV mode."""
        monkeypatch.setattr(cp, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        panel._apply_sav_mode()
        assert panel._sav_mode == SavMode.MANUAL

    def test_apply_clip_mode_settings_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings read failure falls back to manual clipboard mode."""
        monkeypatch.setattr(cp, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        panel._apply_clip_mode()
        assert panel._clip_mode == ClipMode.MANUAL

    def test_apply_sav_mode_switch_stops_active(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching SAV mode stops the previously-active pipeline."""
        settings = _configured(tmp_path)
        settings.sav_processing.mode = SavMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel._sav_mode = SavMode.MANUAL
        panel._sav_listening = True
        panel._apply_sav_mode()
        assert panel._sav_mode == SavMode.MONITOR
        assert panel._sav_listening is False


class TestRemainingBranches:
    """Cover the remaining guard arrows, cached getters, and callbacks."""

    def test_cleanup(self, panel: cp.CapturePanel) -> None:
        """_cleanup unregisters the language callback and stops workers."""
        panel._cleanup()
        assert panel._hotkey_listener is None

    def test_stop_all_workers_not_running(self, panel: cp.CapturePanel) -> None:
        """A scan worker that is not running is not waited on."""
        worker = MagicMock()
        worker.isRunning.return_value = False
        panel._scan_workers = [worker]
        panel._stop_all_workers()
        worker.wait.assert_not_called()

    def test_on_language_changed(self, panel: cp.CapturePanel) -> None:
        """A language change triggers retranslate."""
        panel._on_language_changed("en")
        assert panel.start_stop_button.text() != ""

    def test_get_scan_service_cached(self, panel: cp.CapturePanel) -> None:
        """A cached scan service is returned without rebuilding."""
        cached = MagicMock()
        panel._scan_service = cached
        assert panel._get_scan_service() is cached

    def test_get_clip_service_cached(self, panel: cp.CapturePanel) -> None:
        """A cached clipboard service is returned without rebuilding."""
        cached = MagicMock()
        panel._clip_service = cached
        assert panel._get_clip_service() is cached

    def test_retranslate_while_capturing(self, panel: cp.CapturePanel) -> None:
        """Retranslate sets the stop label while capturing."""
        panel.capturing = True
        panel.retranslate()
        assert panel.start_stop_button.text() != ""

    # ---- capture ----

    def test_on_capture_triggered_no_service(self, panel: cp.CapturePanel) -> None:
        """A hotkey capture with no scan service does nothing."""
        _m("LocalScanService").side_effect = RuntimeError("no db")
        panel._on_capture_triggered()
        assert panel._scan_workers == []

    def test_scan_from_menu_cancelled(self, panel: cp.CapturePanel) -> None:
        """Cancelling the file dialog scans nothing."""
        _m("QFileDialog").getOpenFileName.return_value = ("", "")
        panel.scan_screenshot_from_menu()
        assert panel._scan_workers == []

    def test_process_screenshot_no_service(self, panel: cp.CapturePanel) -> None:
        """A missing scan service skips the file scan."""
        _m("LocalScanService").side_effect = RuntimeError("no db")
        panel.process_screenshot("shot.png")
        assert panel._scan_workers == []

    def test_scan_worker_done_callback_clears_busy(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When a hotkey scan worker finishes, busy clears and it is removed."""
        _use_settings(monkeypatch, _configured(tmp_path))
        monkeypatch.setattr(cp, "LocalScanWorker", FakeScanWorker)
        panel._on_capture_triggered()
        assert panel._capture_busy is True
        worker = panel._scan_workers[0]
        worker.scan_finished.emit(Stockpile())
        assert panel._capture_busy is False
        assert panel._scan_workers == []

    def test_scan_worker_error_callback(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A scan worker error also clears busy and removes the worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        monkeypatch.setattr(cp, "LocalScanWorker", FakeScanWorker)
        panel.process_screenshot("shot.png")
        worker = panel._scan_workers[0]
        worker.scan_error.emit("boom")
        assert panel._scan_workers == []

    # ---- SAV ----

    def test_validate_sav_config_settings_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings read failure yields a validation error."""
        monkeypatch.setattr(cp, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        path, error = panel._validate_sav_config()
        assert path is None
        assert error is not None

    def test_scan_sav_from_menu_success(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A valid config scans the SAV from the menu."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.scan_sav_from_menu()
        assert panel._sav_scan_worker is not None

    def test_on_sav_capture_triggered_error(self, panel: cp.CapturePanel) -> None:
        """The SAV hotkey logs and returns when validation fails."""
        panel._on_sav_capture_triggered()
        assert panel._sav_scan_worker is None

    def test_on_sav_capture_triggered_success(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The SAV hotkey runs a scan when validation passes."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._on_sav_capture_triggered()
        assert panel._sav_scan_worker is not None

    def test_run_sav_scan_output_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A failed output coordinator aborts the one-shot SAV scan."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("OutputCoordinator").side_effect = RuntimeError("bad output")
        panel._run_sav_scan(tmp_path / "db.h5")
        assert panel._sav_scan_worker is None

    def test_apply_sav_mode_switch_stops_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching SAV mode stops an active monitor."""
        settings = _configured(tmp_path)
        settings.sav_processing.mode = SavMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel._sav_mode = SavMode.MANUAL
        panel._sav_monitoring = True
        panel._apply_sav_mode()
        assert panel._sav_monitoring is False

    def test_toggle_all_starts_sav_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts SAV monitoring in monitor mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._sav_mode = SavMode.MONITOR
        panel.toggle_all()
        assert panel._sav_monitoring is True

    def test_toggle_all_stops_everything(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A second toggle stops all running methods."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.toggle_all()
        assert panel._is_active() is True
        panel.toggle_all()
        assert panel._is_active() is False

    def test_toggle_sav_monitor_stop(self, panel: cp.CapturePanel) -> None:
        """Toggling while monitoring stops the SAV monitor."""
        panel._sav_monitoring = True
        panel.toggle_sav_monitor()
        assert panel._sav_monitoring is False

    def test_start_sav_monitor_validation_error(self, panel: cp.CapturePanel) -> None:
        """Starting the SAV monitor warns when no .sav is available."""
        panel.start_sav_monitor()
        assert panel._sav_monitoring is False

    def test_stop_sav_monitor_no_worker(self, panel: cp.CapturePanel) -> None:
        """Stopping with no monitor worker just resets the flag."""
        panel._sav_monitor_worker = None
        panel.stop_sav_monitor()
        assert panel._sav_monitoring is False

    def test_on_sav_monitor_finished_other_sender(self, panel: cp.CapturePanel) -> None:
        """A finished signal from a different worker is ignored."""
        panel._sav_monitor_worker = MagicMock()
        panel._on_sav_monitor_finished(True)  # sender() is None, not the worker
        assert panel._sav_monitor_worker is not None

    # ---- clipboard ----

    def test_apply_clip_mode_switch_stops_listen(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching clipboard mode stops active listening."""
        settings = _configured(tmp_path)
        settings.clipboard.mode = ClipMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel._clip_mode = ClipMode.MANUAL
        panel._clip_listening = True
        panel._apply_clip_mode()
        assert panel._clip_listening is False

    def test_apply_clip_mode_switch_stops_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching clipboard mode stops active monitoring."""
        settings = _configured(tmp_path)
        settings.clipboard.mode = ClipMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel._clip_mode = ClipMode.MANUAL
        panel._clip_monitoring = True
        panel._apply_clip_mode()
        assert panel._clip_monitoring is False

    def test_toggle_all_starts_clip_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts clipboard monitoring in monitor mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel._clip_mode = ClipMode.MONITOR
        panel.toggle_all()
        assert panel._clip_monitoring is True

    def test_toggle_clip_monitor_stop(self, panel: cp.CapturePanel) -> None:
        """Toggling while monitoring stops the clipboard monitor."""
        panel._clip_monitoring = True
        panel.toggle_clip_monitor()
        assert panel._clip_monitoring is False

    def test_on_clip_capture_triggered_no_service(self, panel: cp.CapturePanel) -> None:
        """A clipboard hotkey with no service does nothing."""
        _m("build_clipboard_scan_service").side_effect = RuntimeError("no catalog")
        panel._on_clip_capture_triggered()
        assert panel._clip_scan_worker is None

    def test_start_clip_monitor_no_service(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A clipboard monitor aborts when the service cannot be built."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("build_clipboard_scan_service").side_effect = RuntimeError("no catalog")
        panel.start_clip_monitor()
        assert panel._clip_monitoring is False

    def test_start_clip_monitor_poll_interval_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings failure while reading the poll interval aborts the monitor."""
        panel._clip_service = MagicMock()  # cached so the build is skipped
        monkeypatch.setattr(cp, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        panel.start_clip_monitor()
        assert panel._clip_monitoring is False

    def test_stop_clip_monitor_no_worker(self, panel: cp.CapturePanel) -> None:
        """Stopping with no clipboard monitor worker just resets the flag."""
        panel._clip_monitor_worker = None
        panel.stop_clip_monitor()
        assert panel._clip_monitoring is False

    def test_on_clip_monitor_finished_other_sender(self, panel: cp.CapturePanel) -> None:
        """A finished signal from a different clipboard worker is ignored."""
        panel._clip_monitor_worker = MagicMock()
        panel._on_clip_monitor_finished(True)
        assert panel._clip_monitor_worker is not None
