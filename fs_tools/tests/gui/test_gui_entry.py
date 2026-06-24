"""Tests for the fs-tools GUI entry points (``fs_tools.gui``).

Window classes and the Qt event loop are mocked so the launchers run their
wiring without opening windows or blocking on ``app.exec()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from fs_tools import gui as gui_mod


def test_bootstrap_returns_application(qtbot: Any) -> None:
    """_bootstrap returns the (existing) QApplication instance."""
    assert isinstance(gui_mod._bootstrap(), QApplication)


def test_bootstrap_tolerates_settings_error(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A settings load failure falls back to defaults without raising."""
    monkeypatch.setattr(gui_mod, "AppSettings", MagicMock(side_effect=RuntimeError("boom")))
    assert isinstance(gui_mod._bootstrap(), QApplication)


def test_run_gui(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_gui builds the main window and enters the event loop."""
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    with (
        patch("fs_tools.gui.main_window.ToolsMainWindow") as window,
        pytest.raises(SystemExit),
    ):
        gui_mod.run_gui()
    window.assert_called_once()
    window.return_value.show.assert_called_once()


def test_run_visualizer(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_visualizer opens the visualizer window for the given database."""
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    with (
        patch("fs_tools.gui.windows.database_visualizer_window.DatabaseVisualizerWindow") as window,
        pytest.raises(SystemExit),
    ):
        gui_mod.run_visualizer(Path("db.h5"))
    window.assert_called_once()


def test_run_debug_viewer(qtbot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_debug_viewer opens the debug window and loads the image."""
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    with (
        patch("fs_tools.gui.windows.debug_image_window.DebugImageWindow") as window,
        pytest.raises(SystemExit),
    ):
        gui_mod.run_debug_viewer(Path("shot.png"), Path("db.h5"))
    window.assert_called_once()
    window.return_value.load_image.assert_called_once()
