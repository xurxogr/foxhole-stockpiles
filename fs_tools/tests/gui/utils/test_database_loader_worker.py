"""Tests for DatabaseLoaderWorker."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.gui.utils.database_loader_worker import DatabaseLoaderWorker
from fs_tools.models.icon_template import IconTemplate

MODULE = "fs_tools.gui.utils.database_loader_worker"


def test_initialization() -> None:
    """Test DatabaseLoaderWorker initialization."""
    loader = DatabaseLoaderWorker("/path/to/db.h5")
    assert loader.database_path == "/path/to/db.h5"


def test_run_success(qtbot: Any) -> None:
    """Test successful database loading.

    Args:
        qtbot: PyQt test fixture.
    """
    loader = DatabaseLoaderWorker("/path/to/db.h5")

    mock_databases: dict[SupportedResolution, list[IconTemplate]] = {SupportedResolution.R_1080: []}

    with patch(f"{MODULE}.read_all_resolutions", return_value=mock_databases) as mock_read:
        result: list[Any] = []
        loader.databases_loaded.connect(lambda x: result.append(x))

        loader.run()

        mock_read.assert_called_once_with(Path("/path/to/db.h5"))
        assert len(result) == 1
        assert result[0] == mock_databases


def test_run_error(qtbot: Any) -> None:
    """Test database loading error handling.

    Args:
        qtbot: PyQt test fixture.
    """
    loader = DatabaseLoaderWorker("/path/to/db.h5")

    with patch(
        f"{MODULE}.read_all_resolutions",
        side_effect=FileNotFoundError("Database not found"),
    ):
        errors: list[str] = []
        loader.error.connect(lambda x: errors.append(x))

        loader.run()

        assert len(errors) == 1
        assert "Database not found" in errors[0]
