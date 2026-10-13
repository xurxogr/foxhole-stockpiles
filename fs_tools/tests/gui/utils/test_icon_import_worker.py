"""Tests for IconImportWorker."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fs_tools.gui.utils.icon_import_worker import IconImportWorker

_ADD_MOD = "fs_tools.gui.utils.icon_import_worker.fs_assets.add_mod"
_STATS = {
    "total_items": 380,
    "items_embedded": 120,
    "missing_code": 0,
    "icons_missing": 260,
    "decode_errors": 0,
}


def make_worker(tmp_path: Path, **overrides: Any) -> IconImportWorker:
    """Create a worker importing two mod paks into a not-yet-existing folder.

    Args:
        tmp_path (Path): Temporary directory path.
        **overrides (Any): Constructor arguments to override.

    Returns:
        IconImportWorker: Worker instance.
    """
    kwargs: dict[str, Any] = {
        "mod_pak_files": ["Mod_1.pak", "Mod_2.pak"],
        "mod_name": "  clean icons ",
        "catalog_path": tmp_path / "catalog.json",
        "database_path": tmp_path / "db" / "templates.h5",
        "vanilla_pak_file": "War.pak",
        "resolutions": [1080, 1440],
    }
    kwargs.update(overrides)
    return IconImportWorker(**kwargs)


def _listen(worker: IconImportWorker) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Connect mocks to the worker's signals.

    Args:
        worker (IconImportWorker): The worker to listen to.

    Returns:
        tuple[MagicMock, MagicMock, MagicMock]: finished, error and progress slots.
    """
    finished, error, progress = MagicMock(), MagicMock(), MagicMock()
    worker.finished.connect(finished)
    worker.error.connect(error)
    worker.progress.connect(progress)
    return finished, error, progress


def test_invalid_mod_name_is_rejected_up_front(tmp_path: Path) -> None:
    """An unsafe mod name fails when the worker is created."""
    with pytest.raises(ValueError):
        make_worker(tmp_path, mod_name="../vanilla")


def test_run_adds_the_mod_with_fs_assets(tmp_path: Path) -> None:
    """run() passes every input to fs_assets.add_mod and reports success."""
    worker = make_worker(tmp_path)
    finished, error, progress = _listen(worker)

    with patch(_ADD_MOD, return_value=_STATS) as add_mod:
        worker.run()

    kwargs = add_mod.call_args.kwargs
    assert kwargs["catalog"] == str(tmp_path / "catalog.json")
    assert kwargs["pak"] == ["Mod_1.pak", "Mod_2.pak"]
    assert kwargs["db"] == str(tmp_path / "db" / "templates.h5")
    assert kwargs["mod_name"] == "clean icons"
    assert kwargs["vanilla_pak"] == "War.pak"
    assert kwargs["resolution"] == [1080, 1440]
    assert callable(kwargs["progress"])
    assert (tmp_path / "db").is_dir()
    finished.assert_called_once_with(True)
    error.assert_not_called()
    assert "120" in progress.call_args.args[0]


def test_run_without_vanilla_pak_or_resolutions(tmp_path: Path) -> None:
    """Omitted optional inputs are passed as None (all resolutions, no fallback)."""
    worker = make_worker(tmp_path, vanilla_pak_file=None, resolutions=None)

    with patch(_ADD_MOD, return_value=_STATS) as add_mod:
        worker.run()

    assert add_mod.call_args.kwargs["vanilla_pak"] is None
    assert add_mod.call_args.kwargs["resolution"] is None


def test_stage_starts_are_reported_as_progress(tmp_path: Path) -> None:
    """Each stage reports once when it starts, not on every step."""
    worker = make_worker(tmp_path)
    _, _, progress = _listen(worker)

    def fake_add_mod(**kwargs: Any) -> dict[str, int]:
        report = kwargs["progress"]
        report("extracting_icons", 0, 40)
        report("extracting_icons", 40, 40)
        report("extracting_vanilla_icons", 0, 33)
        report("building_templates", 0, 380)
        report("building_templates", 200, 380)
        return _STATS

    with patch(_ADD_MOD, side_effect=fake_add_mod):
        worker.run()

    messages = [call.args[0] for call in progress.call_args_list]
    assert len(messages) == 4
    assert "40" in messages[0]
    assert "33" in messages[1]
    assert "380" in messages[2]


def test_import_failure_is_reported(tmp_path: Path) -> None:
    """An fs_assets error is emitted and the run ends unsuccessfully."""
    worker = make_worker(tmp_path)
    finished, error, _ = _listen(worker)

    with patch(_ADD_MOD, side_effect=RuntimeError("Mod_1.pak has none of the catalog's icons")):
        worker.run()

    error.assert_called_once_with("Mod_1.pak has none of the catalog's icons")
    finished.assert_called_once_with(False)
