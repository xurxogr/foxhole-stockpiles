"""End-to-end tests of SavPipeline with a real monitor worker thread."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.gui.controllers import sav_pipeline
from foxhole_stockpiles.gui.controllers.sav_pipeline import SavPipeline


@pytest.fixture
def pipeline(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[SavPipeline, MagicMock]:
    """Build a SavPipeline watching a real temp file, reporting to a mock host."""
    sav = tmp_path / "World_MapData.sav"
    sav.write_text("x")
    settings = AppSettings()
    settings.sav_processing.sav_file_path = sav
    settings.sav_processing.poll_interval = 0.01
    monkeypatch.setattr(sav_pipeline, "AppSettings", lambda *a, **k: settings)
    coordinator = MagicMock()
    coordinator.handle_output = AsyncMock(return_value=None)
    monkeypatch.setattr(sav_pipeline, "OutputCoordinator", lambda *a, **k: coordinator)
    parent = QWidget()
    qtbot.addWidget(parent)
    host = MagicMock()
    return SavPipeline(host=host, parent=parent), host


def test_real_monitor_thread_reports_back_on_the_gui_thread(
    qtbot: Any, pipeline: tuple[SavPipeline, MagicMock]
) -> None:
    """Stopping a live monitor clears its state once the thread reports finished."""
    sav, host = pipeline
    with patch(
        "foxhole_stockpiles.services.savefile_processor.parse_save",
        return_value=[],
    ):
        sav.start_monitor()
        assert sav.monitoring is True
        qtbot.waitUntil(lambda: sav._monitor_running(), timeout=2000)

        worker = sav._monitor_worker
        assert worker is not None
        sav.stop_monitor()
        assert sav.monitoring is False
        qtbot.waitUntil(lambda: sav._monitor_worker is None, timeout=5000)
        worker.wait(2000)

    assert host.refresh_controls.call_count >= 3
    assert host.feed.call_count == 2
