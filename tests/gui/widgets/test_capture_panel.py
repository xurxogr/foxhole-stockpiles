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
from foxhole_stockpiles.enums.capture_mode import CaptureMode
from foxhole_stockpiles.gui.controllers import (
    clip_pipeline,
    monitor_pipeline,
    ocr_pipeline,
    sav_pipeline,
)
from foxhole_stockpiles.gui.utils import capture_availability
from foxhole_stockpiles.gui.widgets import capture_panel as cp
from foxhole_stockpiles.i18n import t
from foxhole_stockpiles.models.stockpile import Stockpile

_MODULES = (cp, monitor_pipeline, ocr_pipeline, sav_pipeline, clip_pipeline)


def _owners(name: str) -> list[Any]:
    """Return every panel/pipeline module that imports the given collaborator."""
    return [module for module in _MODULES if hasattr(module, name)]


def _patch(monkeypatch: pytest.MonkeyPatch, name: str, value: Any) -> None:
    """Replace a collaborator in every panel/pipeline module that imports it."""
    for module in _owners(name):
        monkeypatch.setattr(module, name, value)


def _m(name: str) -> MagicMock:
    """Return a module-level collaborator mocked in by the autouse fixture."""
    return cast(MagicMock, getattr(_owners(name)[0], name))


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
        _patch(monkeypatch, name, MagicMock())
    monkeypatch.setattr(cp, "global_hotkeys_supported", lambda: True)
    _patch(monkeypatch, "auto_detect_savefile", lambda: None)
    monkeypatch.setattr(capture_availability, "auto_detect_savefile", lambda: None)


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
    _patch(monkeypatch, "AppSettings", lambda *a, **k: settings)


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
        assert panel.sav_pipeline.listening is False
        assert panel.clip_pipeline.monitoring is False

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
        panel.feed("hello")
        text = panel.activity_feed.toPlainText()
        assert "hello" in text

    def test_clear_logs(self, panel: cp.CapturePanel) -> None:
        """clear_logs empties the activity feed."""
        panel.feed("something")
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
        panel.on_output_response(None)
        assert panel.activity_feed.toPlainText() == ""

    def test_webhook_list_writes_each_message(self, panel: cp.CapturePanel) -> None:
        """A webhook list response writes one feed line per message."""
        panel.clear_logs()
        panel.on_output_response(["Row 1 added", "Row 2 failed"])
        text = panel.activity_feed.toPlainText()
        assert "Row 1 added" in text
        assert "Row 2 failed" in text

    def test_return_dict_writes_json(self, panel: cp.CapturePanel) -> None:
        """A return/sheets dict response is written as JSON text."""
        panel.clear_logs()
        panel.on_output_response({"stockpiles": [{"name": "X"}]})
        text = panel.activity_feed.toPlainText()
        assert "stockpiles" in text
        assert '"name": "X"' in text


class TestAvailabilityHelpers:
    """Static settings-availability helpers."""

    def test_catalog_available(self, tmp_path: Path) -> None:
        """A configured, existing catalog reads as available."""
        settings = _configured(tmp_path)
        assert capture_availability.catalog_available(settings) is True

    def test_catalog_unavailable(self) -> None:
        """No catalog reads as unavailable."""
        assert capture_availability.catalog_available(AppSettings()) is False

    def test_sav_file_available(self, tmp_path: Path) -> None:
        """A configured, existing .sav reads as available."""
        settings = _configured(tmp_path)
        assert capture_availability.sav_file_available(settings) is True

    def test_sav_file_unavailable(self) -> None:
        """No .sav path reads as unavailable."""
        assert capture_availability.sav_file_available(AppSettings()) is False


class TestButtonStatesAndRefresh:
    """Single-button enablement, status labels, and settings refresh."""

    def test_refresh_controls_unconfigured(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With nothing configured, statuses are non-empty and the button is off."""
        _use_settings(monkeypatch, AppSettings())
        panel.refresh_controls()
        assert panel.ocr_status.text() != ""
        # Nothing usable and not running -> the single button is disabled.
        assert panel.start_stop_button.isEnabled() is False

    def test_refresh_controls_configured(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured setup enables the button and shows the OCR key."""
        settings = _configured(tmp_path)
        _use_settings(monkeypatch, settings)
        panel.refresh_controls()
        assert panel.start_stop_button.isEnabled()
        assert panel.ocr_status.text() == settings.scanner.capture_key

    def test_refresh_db_info_resets_services(self, panel: cp.CapturePanel) -> None:
        """refresh_db_info drops cached services."""
        panel.ocr_pipeline._service = MagicMock()
        panel.clip_pipeline._service = MagicMock()
        panel.refresh_db_info()
        assert panel.ocr_pipeline._service is None
        assert panel.clip_pipeline._service is None


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
        panel.feed("old hint")
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
        panel.feed("scan result")
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
        assert panel.is_active() is False

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
        panel.ocr_pipeline._capture_busy = True
        panel.ocr_pipeline.on_capture_triggered()
        # Still busy, no worker spawned.
        assert panel.ocr_pipeline._workers == []

    def test_on_capture_triggered_runs(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A hotkey capture builds and starts a scan worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.ocr_pipeline.on_capture_triggered()
        assert panel.ocr_pipeline._capture_busy is True
        assert len(panel.ocr_pipeline._workers) == 1

    def test_process_screenshot(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A file scan builds and starts a worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.ocr_pipeline.process_screenshot("shot.png")
        assert len(panel.ocr_pipeline._workers) == 1

    def test_process_screenshot_no_service(self, panel: cp.CapturePanel) -> None:
        """No scan service skips the worker."""
        _m("LocalScanService").side_effect = RuntimeError("no db")
        panel.ocr_pipeline.process_screenshot("shot.png")
        assert panel.ocr_pipeline._workers == []

    def test_scan_screenshot_from_menu(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The menu action opens a dialog then scans the chosen file."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("QFileDialog").getOpenFileName.return_value = ("shot.png", "")
        panel.ocr_pipeline.scan_screenshot_from_menu()
        assert len(panel.ocr_pipeline._workers) == 1

    def test_scan_handlers(self, panel: cp.CapturePanel) -> None:
        """Scan finished/error handlers run without error."""
        panel.ocr_pipeline._on_scan_finished(Stockpile())
        panel.ocr_pipeline._on_scan_error("boom")


class TestSav:
    """SAV processing flow."""

    def test_validate_no_sav_file(self, panel: cp.CapturePanel) -> None:
        """No configured/auto-detected .sav yields an error."""
        with pytest.raises(ValueError):
            panel.sav_pipeline._configured_sav_path()

    def test_validate_success(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured, existing .sav validates."""
        _use_settings(monkeypatch, _configured(tmp_path))
        assert panel.sav_pipeline._configured_sav_path().exists()

    def test_validate_missing_file(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A configured-but-missing .sav yields an error."""
        settings = AppSettings()
        settings.sav_processing.sav_file_path = tmp_path / "nope.sav"
        _use_settings(monkeypatch, settings)
        with pytest.raises(ValueError):
            panel.sav_pipeline._configured_sav_path()

    def test_toggle_all_starts_sav_manual(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts SAV listening in manual mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.sav_pipeline.mode = CaptureMode.MANUAL
        panel.toggle_all()
        assert panel.sav_pipeline.listening is True

    def test_start_and_stop_sav_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Monitor mode starts and stops the monitor worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.sav_pipeline.start_monitor()
        assert panel.sav_pipeline.monitoring is True
        panel.sav_pipeline.stop_monitor()
        assert panel.sav_pipeline.monitoring is False

    def test_run_sav_scan(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A one-shot SAV scan starts a worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.sav_pipeline._run_scan(tmp_path / "db.h5")
        assert panel.sav_pipeline._scan_worker is not None

    def test_scan_sav_from_menu_error(self, panel: cp.CapturePanel) -> None:
        """The menu action warns when no .sav is available."""
        panel.sav_pipeline.scan_from_menu()
        _m("QMessageBox").warning.assert_called()

    def test_sav_handlers(self, panel: cp.CapturePanel) -> None:
        """SAV callback handlers run without error."""
        panel.sav_pipeline._on_error("boom")
        panel.sav_pipeline._on_scan_finished(True)
        panel.sav_pipeline._on_monitor_finished(True)

    def test_apply_sav_mode_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Applying monitor mode updates the stored mode."""
        settings = _configured(tmp_path)
        settings.sav_processing.mode = CaptureMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel.sav_pipeline.apply_mode()
        assert panel.sav_pipeline.mode == CaptureMode.MONITOR


class TestClip:
    """Clipboard processing flow."""

    def test_toggle_all_starts_clip_manual(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts clipboard listening in manual mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.clip_pipeline.mode = CaptureMode.MANUAL
        panel.toggle_all()
        assert panel.clip_pipeline.listening is True

    def test_start_and_stop_clip_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Monitor mode primes the service and runs the monitor worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.clip_pipeline.start_monitor()
        assert panel.clip_pipeline.monitoring is True
        panel.clip_pipeline.stop_monitor()
        assert panel.clip_pipeline.monitoring is False

    def test_clip_service_failure_returns_none(self, panel: cp.CapturePanel) -> None:
        """A failed service build yields no clip service."""
        _m("build_clipboard_scan_service").side_effect = RuntimeError("no catalog")
        assert panel.clip_pipeline._get_service() is None

    def test_on_clip_capture_triggered(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A clipboard hotkey starts a one-shot scan worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.clip_pipeline.on_capture_triggered()
        assert panel.clip_pipeline._scan_worker is not None

    def test_clip_handlers(self, panel: cp.CapturePanel) -> None:
        """Clipboard callback handlers run without error."""
        panel.clip_pipeline._on_error("boom")
        panel.clip_pipeline._on_scan_finished(True)
        panel.clip_pipeline._on_monitor_finished(True)
        panel.clip_pipeline._on_stockpile_found(None)
        panel.clip_pipeline._on_stockpile_found(Stockpile())

    def test_apply_clip_mode_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Applying monitor mode updates the stored clipboard mode."""
        settings = _configured(tmp_path)
        settings.clipboard.mode = CaptureMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel.clip_pipeline.apply_mode()
        assert panel.clip_pipeline.mode == CaptureMode.MONITOR


class TestEdgeCases:
    """Guard branches, exception paths, and cleanup."""

    def test_stop_all_workers(self, panel: cp.CapturePanel) -> None:
        """All listeners and running workers are stopped/awaited."""
        panel._hotkey_listener = MagicMock()
        panel._sav_hotkey_listener = MagicMock()
        panel._clip_hotkey_listener = MagicMock()
        scan_worker = MagicMock()
        scan_worker.isRunning.return_value = True
        panel.ocr_pipeline._workers = [scan_worker]
        for pipeline in (panel.sav_pipeline, panel.clip_pipeline):
            for attr in ("_monitor_worker", "_scan_worker"):
                worker = MagicMock()
                worker.isRunning.return_value = True
                setattr(pipeline, attr, worker)

        panel._stop_all_workers()

        assert panel._hotkey_listener is None
        scan_worker.wait.assert_called()
        panel.sav_pipeline._monitor_worker.stop.assert_called_once()

    def test_toggle_all_listener_error_leaves_idle(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A shared listener that fails to start arms no hotkey method."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("HotkeyListener").side_effect = RuntimeError("no backend")
        panel.toggle_all()
        assert panel.capturing is False
        assert panel.sav_pipeline.listening is False
        assert panel.clip_pipeline.listening is False
        assert panel._hotkey_listener is None

    def test_run_sav_scan_already_running(self, panel: cp.CapturePanel) -> None:
        """A SAV scan already in progress is not restarted."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel.sav_pipeline._scan_worker = worker
        panel.sav_pipeline._run_scan(Path("x.sav"))
        assert panel.sav_pipeline._scan_worker is worker

    def test_start_sav_monitor_already_running(self, panel: cp.CapturePanel) -> None:
        """A SAV monitor already running is not restarted."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel.sav_pipeline._monitor_worker = worker
        panel.sav_pipeline.start_monitor()
        assert panel.sav_pipeline.monitoring is False

    def test_clip_capture_triggered_already_running(self, panel: cp.CapturePanel) -> None:
        """A clipboard scan already in progress ignores the hotkey."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel.clip_pipeline._scan_worker = worker
        panel.clip_pipeline.on_capture_triggered()
        assert panel.clip_pipeline._scan_worker is worker

    def test_start_clip_monitor_already_running(self, panel: cp.CapturePanel) -> None:
        """A clipboard monitor already running is not restarted."""
        worker = MagicMock()
        worker.isRunning.return_value = True
        panel.clip_pipeline._monitor_worker = worker
        panel.clip_pipeline.start_monitor()
        assert panel.clip_pipeline.monitoring is False

    def test_start_sav_monitor_output_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A failed output coordinator aborts the SAV monitor start."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("OutputCoordinator").side_effect = RuntimeError("bad output")
        panel.sav_pipeline.start_monitor()
        assert panel.sav_pipeline.monitoring is False

    def test_apply_sav_mode_settings_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings read failure falls back to manual SAV mode."""
        _patch(monkeypatch, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        panel.sav_pipeline.apply_mode()
        assert panel.sav_pipeline.mode == CaptureMode.MANUAL

    def test_apply_clip_mode_settings_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings read failure falls back to manual clipboard mode."""
        _patch(monkeypatch, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        panel.clip_pipeline.apply_mode()
        assert panel.clip_pipeline.mode == CaptureMode.MANUAL

    def test_apply_sav_mode_switch_stops_active(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching SAV mode stops the previously-active pipeline."""
        settings = _configured(tmp_path)
        settings.sav_processing.mode = CaptureMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel.sav_pipeline.mode = CaptureMode.MANUAL
        panel.sav_pipeline.listening = True
        panel.sav_pipeline.apply_mode()
        assert panel.sav_pipeline.mode == CaptureMode.MONITOR
        assert panel.sav_pipeline.listening is False


class TestRemainingBranches:
    """Cover the remaining guard arrows, cached getters, and callbacks."""

    def test_stop_all_workers_not_running(self, panel: cp.CapturePanel) -> None:
        """A scan worker that is not running is not waited on."""
        worker = MagicMock()
        worker.isRunning.return_value = False
        panel.ocr_pipeline._workers = [worker]
        panel._stop_all_workers()
        worker.wait.assert_not_called()

    def test_on_language_changed(self, panel: cp.CapturePanel) -> None:
        """A language change triggers retranslate."""
        panel._on_language_changed("en")
        assert panel.start_stop_button.text() != ""

    def test_get_scan_service_cached(self, panel: cp.CapturePanel) -> None:
        """A cached scan service is returned without rebuilding."""
        cached = MagicMock()
        panel.ocr_pipeline._service = cached
        assert panel.ocr_pipeline._get_service() is cached

    def test_get_clip_service_cached(self, panel: cp.CapturePanel) -> None:
        """A cached clipboard service is returned without rebuilding."""
        cached = MagicMock()
        panel.clip_pipeline._service = cached
        assert panel.clip_pipeline._get_service() is cached

    def test_retranslate_while_capturing(self, panel: cp.CapturePanel) -> None:
        """Retranslate sets the stop label while capturing."""
        panel.capturing = True
        panel.retranslate()
        assert panel.start_stop_button.text() != ""

    # ---- capture ----

    def test_on_capture_triggered_no_service(self, panel: cp.CapturePanel) -> None:
        """A hotkey capture with no scan service does nothing."""
        _m("LocalScanService").side_effect = RuntimeError("no db")
        panel.ocr_pipeline.on_capture_triggered()
        assert panel.ocr_pipeline._workers == []

    def test_scan_from_menu_cancelled(self, panel: cp.CapturePanel) -> None:
        """Cancelling the file dialog scans nothing."""
        _m("QFileDialog").getOpenFileName.return_value = ("", "")
        panel.ocr_pipeline.scan_screenshot_from_menu()
        assert panel.ocr_pipeline._workers == []

    def test_process_screenshot_no_service(self, panel: cp.CapturePanel) -> None:
        """A missing scan service skips the file scan."""
        _m("LocalScanService").side_effect = RuntimeError("no db")
        panel.ocr_pipeline.process_screenshot("shot.png")
        assert panel.ocr_pipeline._workers == []

    def test_scan_worker_done_callback_clears_busy(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When a hotkey scan worker finishes, busy clears and it is removed."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _patch(monkeypatch, "LocalScanWorker", FakeScanWorker)
        panel.ocr_pipeline.on_capture_triggered()
        assert panel.ocr_pipeline._capture_busy is True
        worker = panel.ocr_pipeline._workers[0]
        worker.scan_finished.emit(Stockpile())
        assert panel.ocr_pipeline._capture_busy is False
        assert panel.ocr_pipeline._workers == []

    def test_scan_worker_error_callback(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A scan worker error also clears busy and removes the worker."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _patch(monkeypatch, "LocalScanWorker", FakeScanWorker)
        panel.ocr_pipeline.process_screenshot("shot.png")
        worker = panel.ocr_pipeline._workers[0]
        worker.scan_error.emit("boom")
        assert panel.ocr_pipeline._workers == []

    # ---- SAV ----

    def test_validate_sav_config_settings_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings read failure yields a validation error."""
        _patch(monkeypatch, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        with pytest.raises(ValueError, match="boom"):
            panel.sav_pipeline._configured_sav_path()

    def test_scan_sav_from_menu_success(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A valid config scans the SAV from the menu."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.sav_pipeline.scan_from_menu()
        assert panel.sav_pipeline._scan_worker is not None

    def test_on_sav_capture_triggered_error(self, panel: cp.CapturePanel) -> None:
        """The SAV hotkey logs and returns when validation fails."""
        panel.sav_pipeline.on_capture_triggered()
        assert panel.sav_pipeline._scan_worker is None

    def test_on_sav_capture_triggered_success(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The SAV hotkey runs a scan when validation passes."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.sav_pipeline.on_capture_triggered()
        assert panel.sav_pipeline._scan_worker is not None

    def test_run_sav_scan_output_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A failed output coordinator aborts the one-shot SAV scan."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("OutputCoordinator").side_effect = RuntimeError("bad output")
        panel.sav_pipeline._run_scan(tmp_path / "db.h5")
        assert panel.sav_pipeline._scan_worker is None

    def test_apply_sav_mode_switch_stops_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching SAV mode stops an active monitor."""
        settings = _configured(tmp_path)
        settings.sav_processing.mode = CaptureMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel.sav_pipeline.mode = CaptureMode.MANUAL
        panel.sav_pipeline.monitoring = True
        panel.sav_pipeline.apply_mode()
        assert panel.sav_pipeline.monitoring is False

    def test_toggle_all_starts_sav_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts SAV monitoring in monitor mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.sav_pipeline.mode = CaptureMode.MONITOR
        panel.toggle_all()
        assert panel.sav_pipeline.monitoring is True

    def test_toggle_all_stops_everything(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A second toggle stops all running methods."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.toggle_all()
        assert panel.is_active() is True
        panel.toggle_all()
        assert panel.is_active() is False

    def test_toggle_sav_monitor_stop(self, panel: cp.CapturePanel) -> None:
        """Toggling while monitoring stops the SAV monitor."""
        panel.sav_pipeline.monitoring = True
        panel.sav_pipeline.toggle_monitor()
        assert panel.sav_pipeline.monitoring is False

    def test_start_sav_monitor_validation_error(self, panel: cp.CapturePanel) -> None:
        """Starting the SAV monitor warns when no .sav is available."""
        panel.sav_pipeline.start_monitor()
        assert panel.sav_pipeline.monitoring is False

    def test_stop_sav_monitor_no_worker(self, panel: cp.CapturePanel) -> None:
        """Stopping with no monitor worker just resets the flag."""
        panel.sav_pipeline._monitor_worker = None
        panel.sav_pipeline.stop_monitor()
        assert panel.sav_pipeline.monitoring is False

    def test_on_sav_monitor_finished_other_sender(self, panel: cp.CapturePanel) -> None:
        """A finished signal from a different worker is ignored."""
        panel.sav_pipeline._monitor_worker = MagicMock()
        panel.sav_pipeline._on_monitor_finished(True)  # sender() is None, not the worker
        assert panel.sav_pipeline._monitor_worker is not None

    # ---- clipboard ----

    def test_apply_clip_mode_switch_stops_listen(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching clipboard mode stops active listening."""
        settings = _configured(tmp_path)
        settings.clipboard.mode = CaptureMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel.clip_pipeline.mode = CaptureMode.MANUAL
        panel.clip_pipeline.listening = True
        panel.clip_pipeline.apply_mode()
        assert panel.clip_pipeline.listening is False

    def test_apply_clip_mode_switch_stops_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Switching clipboard mode stops active monitoring."""
        settings = _configured(tmp_path)
        settings.clipboard.mode = CaptureMode.MONITOR
        _use_settings(monkeypatch, settings)
        panel.clip_pipeline.mode = CaptureMode.MANUAL
        panel.clip_pipeline.monitoring = True
        panel.clip_pipeline.apply_mode()
        assert panel.clip_pipeline.monitoring is False

    def test_toggle_all_starts_clip_monitor(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The single button starts clipboard monitoring in monitor mode."""
        _use_settings(monkeypatch, _configured(tmp_path))
        panel.clip_pipeline.mode = CaptureMode.MONITOR
        panel.toggle_all()
        assert panel.clip_pipeline.monitoring is True

    def test_toggle_clip_monitor_stop(self, panel: cp.CapturePanel) -> None:
        """Toggling while monitoring stops the clipboard monitor."""
        panel.clip_pipeline.monitoring = True
        panel.clip_pipeline.toggle_monitor()
        assert panel.clip_pipeline.monitoring is False

    def test_on_clip_capture_triggered_no_service(self, panel: cp.CapturePanel) -> None:
        """A clipboard hotkey with no service does nothing."""
        _m("build_clipboard_scan_service").side_effect = RuntimeError("no catalog")
        panel.clip_pipeline.on_capture_triggered()
        assert panel.clip_pipeline._scan_worker is None

    def test_start_clip_monitor_no_service(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A clipboard monitor aborts when the service cannot be built."""
        _use_settings(monkeypatch, _configured(tmp_path))
        _m("build_clipboard_scan_service").side_effect = RuntimeError("no catalog")
        panel.clip_pipeline.start_monitor()
        assert panel.clip_pipeline.monitoring is False

    def test_start_clip_monitor_poll_interval_error(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A settings failure while reading the poll interval aborts the monitor."""
        panel.clip_pipeline._service = MagicMock()  # cached so the build is skipped
        _patch(monkeypatch, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
        panel.clip_pipeline.start_monitor()
        assert panel.clip_pipeline.monitoring is False

    def test_stop_clip_monitor_no_worker(self, panel: cp.CapturePanel) -> None:
        """Stopping with no clipboard monitor worker just resets the flag."""
        panel.clip_pipeline._monitor_worker = None
        panel.clip_pipeline.stop_monitor()
        assert panel.clip_pipeline.monitoring is False

    def test_on_clip_monitor_finished_other_sender(self, panel: cp.CapturePanel) -> None:
        """A finished signal from a different clipboard worker is ignored."""
        panel.clip_pipeline._monitor_worker = MagicMock()
        panel.clip_pipeline._on_monitor_finished(True)
        assert panel.clip_pipeline._monitor_worker is not None


class TestHotkeysUnavailableHint:
    """The first hint says why configured keys can't be used on this machine."""

    def test_configured_keys_are_not_reported_as_missing(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A key in the settings is not "nothing set up" when only the platform lacks them."""
        settings = AppSettings()
        settings.sav_processing.sav_capture_key = "Ctrl+F3"
        _use_settings(monkeypatch, settings)
        panel._hotkeys_available = False
        panel._get_started_shown = False
        panel.clear_logs()

        panel._maybe_prompt_setup()

        text = panel.activity_feed.toPlainText()
        assert t("activity.hotkeys_unavailable") in text
        assert t("activity.get_started") not in text

    def test_without_any_key_the_hint_stays_the_same(
        self, panel: cp.CapturePanel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With nothing configured, setting something up is still the right advice."""
        _use_settings(monkeypatch, AppSettings())
        panel._hotkeys_available = False
        panel._get_started_shown = False
        panel.clear_logs()

        panel._maybe_prompt_setup()

        assert t("activity.get_started") in panel.activity_feed.toPlainText()
