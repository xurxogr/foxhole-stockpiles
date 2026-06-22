"""Tests for IconImportWorker.

The IconImportWorker is a thin wrapper around ModImporter that provides
Qt signals and threading. The actual import logic is tested in
tests/services/test_mod_importer.py.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.core.settings.sections.database_builder import DatabaseBuilderSettings
from foxhole_stockpiles.core.settings.sections.external_tools import ExternalToolsSettings
from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from fs_tools.gui.utils.icon_import_worker import IconImportWorker
from fs_tools.models.mod_import_progress import ModImportProgress
from fs_tools.models.mod_import_result import ModImportResult


@pytest.fixture
def mock_settings(tmp_path: Path) -> AppSettings:
    """Create mock settings for testing.

    Args:
        tmp_path: Temporary directory path

    Returns:
        AppSettings: Mock settings
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("{}")

    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.write_text("")

    converter_tool = tmp_path / "umodel.exe"
    converter_tool.write_text("")

    database_path = tmp_path / "database.h5"

    return AppSettings(
        database_builder=DatabaseBuilderSettings(
            catalog_file=catalog_file,
            target_resolutions=None,
        ),
        external_tools=ExternalToolsSettings(
            repak=extractor_tool,
            umodel=converter_tool,
        ),
        scanner=ScannerSettings(
            database_path=database_path,
        ),
    )


@pytest.fixture
def worker(tmp_path: Path, mock_settings: AppSettings) -> IconImportWorker:
    """Create an IconImportWorker instance.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings

    Returns:
        IconImportWorker: Worker instance
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    catalog_path = tmp_path / "catalog.json"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        worker = IconImportWorker(
            mod_pak_files=[str(pak_file)],
            mod_name="test_mod",
            catalog_path=catalog_path,
            overwrite=False,
        )

    return worker


# ===== Initialization Tests =====


def test_initialization(worker: IconImportWorker, tmp_path: Path) -> None:
    """Test IconImportWorker initialization.

    Args:
        worker: IconImportWorker instance
        tmp_path: Temporary directory path
    """
    assert worker.mod_pak_files == [str(tmp_path / "test.pak")]
    assert worker.mod_name == "test_mod"
    assert worker.catalog_path == tmp_path / "catalog.json"
    assert worker.overwrite is False
    assert worker.vanilla_pak_file is None
    assert worker._should_stop is False
    assert worker.settings is not None


def test_initialization_with_vanilla_pak(tmp_path: Path, mock_settings: AppSettings) -> None:
    """Test IconImportWorker initialization with vanilla PAK file.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    vanilla_pak = tmp_path / "vanilla.pak"
    vanilla_pak.write_text("")

    catalog_path = tmp_path / "catalog.json"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        worker = IconImportWorker(
            mod_pak_files=[str(pak_file)],
            mod_name="test_mod",
            catalog_path=catalog_path,
            overwrite=False,
            vanilla_pak_file=str(vanilla_pak),
        )

    assert worker.vanilla_pak_file == str(vanilla_pak)


def test_initialization_with_overwrite(tmp_path: Path, mock_settings: AppSettings) -> None:
    """Test IconImportWorker initialization with overwrite flag.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    catalog_path = tmp_path / "catalog.json"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        worker = IconImportWorker(
            mod_pak_files=[str(pak_file)],
            mod_name="test_mod",
            catalog_path=catalog_path,
            overwrite=True,
        )

    assert worker.overwrite is True


def test_initialization_with_custom_database_path(
    tmp_path: Path, mock_settings: AppSettings
) -> None:
    """Test IconImportWorker initialization with custom database path.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    catalog_path = tmp_path / "catalog.json"
    custom_db_path = tmp_path / "custom_database.h5"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        worker = IconImportWorker(
            mod_pak_files=[str(pak_file)],
            mod_name="test_mod",
            catalog_path=catalog_path,
            database_path=custom_db_path,
        )

    assert worker.database_path == custom_db_path


# ===== Mod Name Validation Tests =====
# Note: Full validation tests are in test_mod_importer.py
# These tests verify the worker delegates validation correctly


def test_mod_name_validation_invalid_raises(tmp_path: Path, mock_settings: AppSettings) -> None:
    """Test that invalid mod names raise ValueError.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    catalog_path = tmp_path / "catalog.json"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="can only contain alphanumeric"):
            IconImportWorker(
                mod_pak_files=[str(pak_file)],
                mod_name="../etc/passwd",
                catalog_path=catalog_path,
            )


def test_mod_name_validation_empty_raises(tmp_path: Path, mock_settings: AppSettings) -> None:
    """Test that empty mod names raise ValueError.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    catalog_path = tmp_path / "catalog.json"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="Mod name cannot be empty"):
            IconImportWorker(
                mod_pak_files=[str(pak_file)],
                mod_name="",
                catalog_path=catalog_path,
            )


# ===== Stop Tests =====


def test_stop(worker: IconImportWorker) -> None:
    """Test stop method sets the flag.

    Args:
        worker: IconImportWorker instance
    """
    assert worker._should_stop is False
    worker.stop()
    assert worker._should_stop is True


# ===== Progress Callback Tests =====


def test_on_progress_emits_signal(worker: IconImportWorker) -> None:
    """Test that _on_progress emits the progress signal.

    Args:
        worker: IconImportWorker instance
    """
    worker.progress = MagicMock()

    progress = ModImportProgress(
        current_step=1,
        step_name="Extracting",
        message="Test message",
    )

    worker._on_progress(progress)

    worker.progress.emit.assert_called_once_with(1, "Test message")


def test_check_cancel_returns_should_stop(worker: IconImportWorker) -> None:
    """Test that _check_cancel returns _should_stop value.

    Args:
        worker: IconImportWorker instance
    """
    assert worker._check_cancel() is False
    worker._should_stop = True
    assert worker._check_cancel() is True


# ===== Run Method Tests =====


def test_run_calls_asyncio_run(worker: IconImportWorker) -> None:
    """Test the run method calls asyncio.run.

    Args:
        worker: IconImportWorker instance
    """
    with patch("asyncio.run") as mock_asyncio_run:
        worker.run()

        mock_asyncio_run.assert_called_once()


def test_run_exception_handling(worker: IconImportWorker) -> None:
    """Test run method handles exceptions.

    Args:
        worker: IconImportWorker instance
    """
    mock_error = MagicMock()
    mock_finished = MagicMock()

    with patch.object(worker, "error", mock_error):
        with patch.object(worker, "finished", mock_finished):
            with patch("asyncio.run", side_effect=Exception("Test error")):
                worker.run()

                mock_error.emit.assert_called_once_with("Test error")
                mock_finished.emit.assert_called_once_with(False)


# ===== Import Pipeline Tests =====


@pytest.mark.asyncio
async def test_run_import_success(worker: IconImportWorker) -> None:
    """Test successful import execution.

    Args:
        worker: IconImportWorker instance
    """
    mock_finished = MagicMock()
    mock_result = ModImportResult(success=True, templates_added=10)

    with patch.object(worker, "finished", mock_finished):
        with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
            mock_importer = MagicMock()
            mock_importer.run = AsyncMock(return_value=mock_result)
            mock_importer_class.return_value = mock_importer

            await worker._run_import()

            mock_finished.emit.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_run_import_failure(worker: IconImportWorker) -> None:
    """Test import failure handling.

    Args:
        worker: IconImportWorker instance
    """
    mock_finished = MagicMock()
    mock_error = MagicMock()
    mock_result = ModImportResult(success=False, error_message="Test failure")

    with patch.object(worker, "finished", mock_finished):
        with patch.object(worker, "error", mock_error):
            with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
                mock_importer = MagicMock()
                mock_importer.run = AsyncMock(return_value=mock_result)
                mock_importer_class.return_value = mock_importer

                await worker._run_import()

                mock_error.emit.assert_called_once_with("Test failure")
                mock_finished.emit.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_run_import_cancelled(worker: IconImportWorker) -> None:
    """Test import cancelled handling.

    Args:
        worker: IconImportWorker instance
    """
    mock_finished = MagicMock()
    worker._should_stop = True
    mock_result = ModImportResult(success=True)

    with patch.object(worker, "finished", mock_finished):
        with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
            mock_importer = MagicMock()
            mock_importer.run = AsyncMock(return_value=mock_result)
            mock_importer_class.return_value = mock_importer

            await worker._run_import()

            # Should emit False due to cancellation
            mock_finished.emit.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_run_import_exception(worker: IconImportWorker) -> None:
    """Test import exception handling.

    Args:
        worker: IconImportWorker instance
    """
    mock_finished = MagicMock()
    mock_error = MagicMock()

    with patch.object(worker, "finished", mock_finished):
        with patch.object(worker, "error", mock_error):
            with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
                mock_importer_class.side_effect = Exception("Unexpected error")

                await worker._run_import()

                # Should emit error with traceback
                mock_error.emit.assert_called_once()
                error_msg = mock_error.emit.call_args[0][0]
                assert "Unexpected error" in error_msg
                assert "Exception:" in error_msg

                mock_finished.emit.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_run_import_creates_correct_config(
    worker: IconImportWorker, mock_settings: AppSettings
) -> None:
    """Test that run_import creates correct ModImportConfig.

    Args:
        worker: IconImportWorker instance
        mock_settings: Mock settings
    """
    mock_finished = MagicMock()
    mock_result = ModImportResult(success=True)

    with patch.object(worker, "finished", mock_finished):
        with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
            mock_importer = MagicMock()
            mock_importer.run = AsyncMock(return_value=mock_result)
            mock_importer_class.return_value = mock_importer

            await worker._run_import()

            # Verify ModImporter was called with correct config
            call_kwargs = mock_importer_class.call_args[1]
            config = call_kwargs["config"]

            assert config.mod_pak_files == worker.mod_pak_files
            assert config.mod_name == worker.mod_name
            assert config.catalog_path == worker.catalog_path
            assert config.overwrite == worker.overwrite
            assert config.vanilla_pak_file == worker.vanilla_pak_file


@pytest.mark.asyncio
async def test_run_import_passes_callbacks(worker: IconImportWorker) -> None:
    """Test that run_import passes progress and cancel callbacks.

    Args:
        worker: IconImportWorker instance
    """
    mock_finished = MagicMock()
    mock_result = ModImportResult(success=True)

    with patch.object(worker, "finished", mock_finished):
        with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
            mock_importer = MagicMock()
            mock_importer.run = AsyncMock(return_value=mock_result)
            mock_importer_class.return_value = mock_importer

            await worker._run_import()

            # Verify callbacks were passed
            call_kwargs = mock_importer_class.call_args[1]

            assert call_kwargs["progress_callback"] == worker._on_progress
            assert call_kwargs["cancel_check"] == worker._check_cancel


@pytest.mark.asyncio
async def test_run_import_uses_custom_database_path(
    tmp_path: Path, mock_settings: AppSettings
) -> None:
    """Test that run_import uses custom database path when provided.

    Args:
        tmp_path: Temporary directory path
        mock_settings: Mock settings
    """
    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    catalog_path = tmp_path / "catalog.json"
    custom_db_path = tmp_path / "custom_database.h5"

    with patch("fs_tools.gui.utils.icon_import_worker.get_settings", return_value=mock_settings):
        worker = IconImportWorker(
            mod_pak_files=[str(pak_file)],
            mod_name="test_mod",
            catalog_path=catalog_path,
            database_path=custom_db_path,
        )

    mock_finished = MagicMock()
    mock_result = ModImportResult(success=True)

    with patch.object(worker, "finished", mock_finished):
        with patch("fs_tools.gui.utils.icon_import_worker.ModImporter") as mock_importer_class:
            mock_importer = MagicMock()
            mock_importer.run = AsyncMock(return_value=mock_result)
            mock_importer_class.return_value = mock_importer

            await worker._run_import()

            # Verify custom database path was used
            call_kwargs = mock_importer_class.call_args[1]
            config = call_kwargs["config"]
            assert config.database_path == custom_db_path
