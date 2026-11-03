"""The workers report what the real fs-assets raises, whatever its type."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import fs_assets
import pytest

from fs_tools.gui.utils.catalog_builder_worker import CatalogBuilderWorker
from fs_tools.gui.utils.database_loader_worker import DatabaseLoaderWorker
from fs_tools.gui.utils.icon_import_worker import IconImportWorker
from fs_tools.gui.utils.pak_coverage_worker import PakCoverageWorker


def _openable_pak(folder: Path) -> Path:
    """Pack a pak that opens, but holds nothing the game uses.

    Args:
        folder (Path): Where to work.

    Returns:
        Path: The pak.
    """
    content = folder / "src" / "War" / "Content"
    content.mkdir(parents=True)
    (content / "a.txt").write_text("hello", encoding="utf-8")
    pak = folder / "good.pak"
    fs_assets.pack(folder / "src", pak)
    return pak


def _run_catalog_build(worker: CatalogBuilderWorker) -> tuple[MagicMock, MagicMock]:
    """Run a catalog build, listening to how it ends.

    Args:
        worker (CatalogBuilderWorker): The worker.

    Returns:
        tuple[MagicMock, MagicMock]: The finished and error slots.
    """
    finished, error = MagicMock(), MagicMock()
    worker.finished.connect(finished)
    worker.error.connect(error)
    worker.run()
    return finished, error


def test_catalog_build_reports_a_missing_pak(tmp_path: Path) -> None:
    """A missing file raises FileNotFoundError, an OSError."""
    finished, error = _run_catalog_build(
        CatalogBuilderWorker(pak_file=tmp_path / "missing.pak", output_path=tmp_path / "c.json")
    )

    error.assert_called_once()
    assert "missing.pak" in error.call_args.args[0]
    finished.assert_called_once_with(False)


def test_catalog_build_reports_a_broken_pak(tmp_path: Path) -> None:
    """A file that is not a pak raises RuntimeError."""
    pak = tmp_path / "bad.pak"
    pak.write_bytes(b"not a pak")

    finished, error = _run_catalog_build(
        CatalogBuilderWorker(pak_file=pak, output_path=tmp_path / "c.json")
    )

    error.assert_called_once()
    finished.assert_called_once_with(False)


def test_cancelling_a_real_catalog_build_is_not_an_error(tmp_path: Path) -> None:
    """The exception raised from the progress callback comes back unchanged."""
    output = tmp_path / "c.json"
    worker = CatalogBuilderWorker(pak_file=_openable_pak(tmp_path), output_path=output)
    worker.stop()

    finished, error = _run_catalog_build(worker)

    error.assert_not_called()
    finished.assert_called_once_with(False)
    assert not output.exists()


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"resolutions": [999]}, id="ValueError-resolution"),
        pytest.param({"mod_pak_files": []}, id="ValueError-no-paks"),
        pytest.param({"catalog_path": Path("missing.json")}, id="RuntimeError-catalog"),
    ],
)
def test_import_reports_what_add_mod_refuses(tmp_path: Path, overrides: dict[str, Any]) -> None:
    """Invalid arguments raise ValueError since fs-assets checks them first."""
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    arguments: dict[str, Any] = {
        "mod_pak_files": [str(tmp_path / "mod.pak")],
        "mod_name": "mod",
        "catalog_path": catalog,
        "database_path": tmp_path / "db.h5",
        **overrides,
    }
    worker = IconImportWorker(**arguments)
    finished, error = MagicMock(), MagicMock()
    worker.finished.connect(finished)
    worker.error.connect(error)

    worker.run()

    error.assert_called_once()
    finished.assert_called_once_with(False)


@pytest.mark.parametrize(
    "pak_files",
    [pytest.param([], id="ValueError-no-paks"), pytest.param(["a.pak"], id="RuntimeError-catalog")],
)
def test_coverage_reports_what_it_refuses(tmp_path: Path, pak_files: list[str]) -> None:
    """Both an invalid argument and a failed check reach the failed signal."""
    worker = PakCoverageWorker(catalog_path=tmp_path / "missing.json", pak_files=pak_files)
    ready, failed = MagicMock(), MagicMock()
    worker.coverage_ready.connect(ready)
    worker.failed.connect(failed)

    worker.run()

    failed.assert_called_once()
    ready.assert_not_called()


@pytest.mark.parametrize(
    "content",
    [pytest.param(None, id="FileNotFoundError"), pytest.param(b"not hdf5", id="RuntimeError")],
)
def test_loading_reports_an_unusable_database(tmp_path: Path, content: bytes | None) -> None:
    """A missing database and one that is not valid are both reported."""
    database = tmp_path / "db.h5"
    if content is not None:
        database.write_bytes(content)
    loader = DatabaseLoaderWorker(str(database))
    loaded, error = MagicMock(), MagicMock()
    loader.databases_loaded.connect(loaded)
    loader.error.connect(error)

    loader.run()

    error.assert_called_once()
    loaded.assert_not_called()
