"""Tests for CatalogBuilderWorker."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fs_tools.gui.utils.catalog_builder_worker import CatalogBuilderWorker

_BUILD_CATALOG = "fs_tools.gui.utils.catalog_builder_worker.fs_assets.build_catalog"
_STATS = {"total_files": 10, "parsed": 10, "stockpilable": 4, "errors": 0}


@pytest.fixture
def worker(tmp_path: Path) -> CatalogBuilderWorker:
    """Create a CatalogBuilderWorker writing into a not-yet-existing folder.

    Args:
        tmp_path (Path): Temporary directory path.

    Returns:
        CatalogBuilderWorker: Worker instance.
    """
    return CatalogBuilderWorker(
        pak_file=tmp_path / "War.pak",
        output_path=tmp_path / "out" / "catalog.json",
        full=True,
    )


def _listen(worker: CatalogBuilderWorker) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Connect mocks to the worker's signals.

    Args:
        worker (CatalogBuilderWorker): The worker to listen to.

    Returns:
        tuple[MagicMock, MagicMock, MagicMock]: finished, error and progress slots.
    """
    finished, error, progress = MagicMock(), MagicMock(), MagicMock()
    worker.finished.connect(finished)
    worker.error.connect(error)
    worker.progress.connect(progress)
    return finished, error, progress


def test_run_builds_the_catalog_from_the_pak(worker: CatalogBuilderWorker, tmp_path: Path) -> None:
    """run() calls fs_assets with the pak, output and full flag, then reports success."""
    finished, error, progress = _listen(worker)

    with patch(_BUILD_CATALOG, return_value=_STATS) as build:
        worker.run()

    kwargs = build.call_args.kwargs
    assert kwargs["pak"] == str(tmp_path / "War.pak")
    assert kwargs["output"] == str(tmp_path / "out" / "catalog.json")
    assert kwargs["full"] is True
    assert callable(kwargs["progress"])
    assert (tmp_path / "out").is_dir()
    finished.assert_called_once_with(True)
    error.assert_not_called()
    assert "4" in progress.call_args.args[0]


def test_stage_starts_are_reported_as_progress(worker: CatalogBuilderWorker) -> None:
    """Each stage reports once when it starts, not on every step."""
    _, _, progress = _listen(worker)

    def fake_build(**kwargs: Any) -> dict[str, int]:
        report = kwargs["progress"]
        report("extracting_catalog_inputs", 0, 5)
        report("extracting_catalog_inputs", 5, 5)
        report("building_catalog", 0, 7)
        report("building_catalog", 3, 7)
        return _STATS

    with patch(_BUILD_CATALOG, side_effect=fake_build):
        worker.run()

    messages = [call.args[0] for call in progress.call_args_list]
    assert len(messages) == 3
    assert "5" in messages[0]
    assert "7" in messages[1]


def test_build_failure_is_reported(worker: CatalogBuilderWorker) -> None:
    """An fs_assets error is emitted and the run ends unsuccessfully."""
    finished, error, _ = _listen(worker)

    with patch(_BUILD_CATALOG, side_effect=RuntimeError("pak has no catalog inputs")):
        worker.run()

    error.assert_called_once_with("pak has no catalog inputs")
    finished.assert_called_once_with(False)


def test_stop_cancels_through_the_progress_callback(worker: CatalogBuilderWorker) -> None:
    """After stop(), the next progress report aborts the build without an error."""
    finished, error, _ = _listen(worker)

    def fake_build(**kwargs: Any) -> dict[str, int]:
        worker.stop()
        kwargs["progress"]("building_catalog", 1, 7)
        return _STATS

    with patch(_BUILD_CATALOG, side_effect=fake_build):
        worker.run()

    finished.assert_called_once_with(False)
    error.assert_not_called()
