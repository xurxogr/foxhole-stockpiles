"""Tests for commands.add_mod.add_mod module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from fs_tools.commands.add_mod.add_mod import print_progress, run
from fs_tools.models.mod_import_progress import ModImportProgress
from fs_tools.models.mod_import_result import ModImportResult


class TestPrintProgress:
    """Test suite for print_progress function."""

    def test_print_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test printing error progress."""
        progress = ModImportProgress(
            current_step=1,
            step_name="Test",
            message="Test message",
            is_error=True,
            error_message="Something went wrong",
        )

        print_progress(progress)

        captured = capsys.readouterr()
        assert "ERROR:" in captured.err
        assert "Something went wrong" in captured.err

    def test_print_complete(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test printing complete progress."""
        progress = ModImportProgress(
            current_step=4,
            total_steps=4,
            step_name="Complete",
            message="All done",
            is_complete=True,
        )

        print_progress(progress)

        captured = capsys.readouterr()
        assert "[4/4]" in captured.out
        assert "All done" in captured.out

    def test_print_in_progress(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test printing in-progress step."""
        progress = ModImportProgress(
            current_step=2,
            total_steps=4,
            step_name="Extracting",
            message="Processing files",
        )

        print_progress(progress)

        captured = capsys.readouterr()
        assert "[2/4]" in captured.out
        assert "Extracting:" in captured.out
        assert "Processing files" in captured.out


class TestRunFunction:
    """Test suite for the run function."""

    @pytest.fixture
    def mock_settings(self, tmp_path: Path) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.database_builder.catalog_file = tmp_path / "catalog.json"
        settings.database_builder.target_resolutions = None
        settings.database_builder.workers = None
        settings.external_tools.repak = tmp_path / "repak.exe"
        settings.external_tools.umodel = tmp_path / "umodel.exe"
        settings.scanner.database_path = tmp_path / "database.h5"
        settings.templates = None
        settings.logging = MagicMock()
        settings.logging.log_level = "INFO"
        settings.logging.log_file = None

        # Create the files
        (tmp_path / "catalog.json").touch()
        (tmp_path / "repak.exe").touch()
        (tmp_path / "umodel.exe").touch()

        return settings

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_success(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful run execution."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True, templates_added=10)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file])

        mock_importer_class.assert_called_once()
        mock_importer.run.assert_called_once()

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_failure_exits_with_code_1(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits with code 1 on failure."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=False, error_message="Test error")
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 1

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_missing_catalog_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when catalog is not configured."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = None
        mock_settings.scanner.database_path = tmp_path / "db.h5"
        mock_settings.external_tools.repak = tmp_path / "repak.exe"
        mock_settings.external_tools.umodel = tmp_path / "umodel.exe"

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file], catalog=None)

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_pak_not_found_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when PAK file doesn't exist."""
        nonexistent_pak = tmp_path / "nonexistent.pak"

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[nonexistent_pak])

        assert exc_info.value.exit_code == 1

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_invalid_resolution_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits with invalid resolution."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(
                mod_name="TestMod",
                pak_files=[pak_file],
                resolutions=["invalid_resolution"],
            )

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_with_overwrite_flag(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run passes overwrite flag correctly."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file], overwrite=True)

        call_kwargs = mock_importer_class.call_args[1]
        config = call_kwargs["config"]
        assert config.overwrite is True

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_with_vanilla_pak(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run passes vanilla PAK file correctly."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        vanilla_pak = tmp_path / "vanilla.pak"
        vanilla_pak.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file], vanilla_pak=vanilla_pak)

        call_kwargs = mock_importer_class.call_args[1]
        config = call_kwargs["config"]
        assert config.vanilla_pak_file == str(vanilla_pak)

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_quiet_mode_no_callback(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run doesn't pass progress callback in quiet mode."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file], quiet=True)

        call_kwargs = mock_importer_class.call_args[1]
        assert call_kwargs["progress_callback"] is None

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_verbose_mode(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run sets log level to DEBUG in verbose mode."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file], verbose=True)

        # Verify setup_logging was called with DEBUG level
        call_args = mock_setup_logging.call_args[0][0]
        assert call_args.log_level == "DEBUG"

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_missing_database_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when database path is not configured."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = tmp_path / "catalog.json"
        mock_settings.external_tools.repak = tmp_path / "repak.exe"
        mock_settings.external_tools.umodel = tmp_path / "umodel.exe"
        mock_settings.scanner.database_path = None
        mock_settings.logging = MagicMock()
        mock_settings.logging.log_level = "INFO"
        mock_settings.logging.log_file = None

        (tmp_path / "catalog.json").touch()
        (tmp_path / "repak.exe").touch()
        (tmp_path / "umodel.exe").touch()

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_missing_extractor_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when extractor tool is not configured."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = tmp_path / "catalog.json"
        mock_settings.external_tools.repak = None
        mock_settings.external_tools.umodel = tmp_path / "umodel.exe"
        mock_settings.scanner.database_path = tmp_path / "db.h5"
        mock_settings.logging = MagicMock()
        mock_settings.logging.log_level = "INFO"
        mock_settings.logging.log_file = None

        (tmp_path / "catalog.json").touch()
        (tmp_path / "umodel.exe").touch()

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_missing_converter_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when converter tool is not configured."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = tmp_path / "catalog.json"
        mock_settings.external_tools.repak = tmp_path / "repak.exe"
        mock_settings.external_tools.umodel = None
        mock_settings.scanner.database_path = tmp_path / "db.h5"
        mock_settings.logging = MagicMock()
        mock_settings.logging.log_level = "INFO"
        mock_settings.logging.log_file = None

        (tmp_path / "catalog.json").touch()
        (tmp_path / "repak.exe").touch()

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_vanilla_pak_not_found_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when vanilla PAK file doesn't exist."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        vanilla_pak = tmp_path / "nonexistent_vanilla.pak"

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file], vanilla_pak=vanilla_pak)

        assert exc_info.value.exit_code == 1

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_valid_resolution(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run handles valid resolutions correctly."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file], resolutions=["1080", "1440"])

        call_kwargs = mock_importer_class.call_args[1]
        config = call_kwargs["config"]
        assert config.target_resolutions == ["1080", "1440"]

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_uses_settings_resolutions(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run uses target_resolutions from settings when not provided."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = tmp_path / "catalog.json"
        mock_settings.database_builder.target_resolutions = ["1080", "2160"]
        mock_settings.database_builder.workers = None
        mock_settings.external_tools.repak = tmp_path / "repak.exe"
        mock_settings.external_tools.umodel = tmp_path / "umodel.exe"
        mock_settings.scanner.database_path = tmp_path / "database.h5"
        mock_settings.templates = None
        mock_settings.logging = MagicMock()
        mock_settings.logging.log_level = "INFO"
        mock_settings.logging.log_file = None

        (tmp_path / "catalog.json").touch()
        (tmp_path / "repak.exe").touch()
        (tmp_path / "umodel.exe").touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file])

        call_kwargs = mock_importer_class.call_args[1]
        config = call_kwargs["config"]
        assert config.target_resolutions == ["1080", "2160"]

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_success_with_skipped_and_warnings(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test run prints skipped templates and warnings."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(
            success=True,
            templates_added=5,
            templates_skipped=3,
            warnings=["Warning 1", "Warning 2"],
        )
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(mod_name="TestMod", pak_files=[pak_file])

        captured = capsys.readouterr()
        assert "Templates added: 5" in captured.out
        assert "Templates skipped (already in database): 3" in captured.out
        assert "Warnings:" in captured.out
        assert "Warning 1" in captured.out
        assert "Warning 2" in captured.out

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_value_error_handling(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test run handles ValueError exceptions."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_importer_class.side_effect = ValueError("Invalid configuration")

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Configuration error:" in captured.err
        assert "Invalid configuration" in captured.err

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_file_not_found_error_handling(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test run handles FileNotFoundError exceptions."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_importer_class.side_effect = FileNotFoundError("Required file missing")

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "File not found:" in captured.err
        assert "Required file missing" in captured.err

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_generic_exception_handling(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test run handles generic exceptions."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        mock_importer_class.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(typer.Exit) as exc_info:
            await run(mod_name="TestMod", pak_files=[pak_file])

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Unexpected error" in captured.err

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_extract_only_without_extract_dir_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when extract_only is used without extract_dir."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()

        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(
                mod_name="TestMod",
                pak_files=[pak_file],
                extract_dir=None,
                extract_only=True,  # extract_only without extract_dir
            )

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_extract_only_with_extract_dir(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run passes extract_dir and extract_only correctly."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()
        extract_dir = tmp_path / "extract"

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True, templates_added=10)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(
            mod_name="TestMod",
            pak_files=[pak_file],
            extract_dir=extract_dir,
            extract_only=True,
        )

        call_kwargs = mock_importer_class.call_args[1]
        config = call_kwargs["config"]
        assert config.extract_dir == extract_dir
        assert config.extract_only is True

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_preextracted_assets_no_pak_required(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run allows no PAK files when using pre-extracted assets."""
        extract_dir = tmp_path / "extract"

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True, templates_added=10)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(
            mod_name="TestMod",
            pak_files=None,  # No PAK files
            extract_dir=extract_dir,
            extract_only=False,  # Using pre-extracted
        )

        call_kwargs = mock_importer_class.call_args[1]
        config = call_kwargs["config"]
        assert config.mod_pak_files == []
        assert config.extract_dir == extract_dir
        assert config.extract_only is False

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    async def test_run_no_pak_without_extract_dir_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test run exits when no PAK files and no extract_dir."""
        mock_get_settings.return_value = mock_settings

        with pytest.raises(typer.Exit) as exc_info:
            await run(
                mod_name="TestMod",
                pak_files=None,  # No PAK files
                extract_dir=None,  # No extract_dir
                extract_only=False,
            )

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.add_mod.add_mod.get_settings")
    @patch("fs_tools.commands.add_mod.add_mod.setup_logging")
    @patch("fs_tools.commands.add_mod.add_mod.ModImporter")
    async def test_run_extract_only_success_message(
        self,
        mock_importer_class: MagicMock,
        mock_setup_logging: MagicMock,
        mock_get_settings: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test run prints correct success message for extract_only."""
        pak_file = tmp_path / "mod.pak"
        pak_file.touch()
        extract_dir = tmp_path / "extract"

        mock_get_settings.return_value = mock_settings

        mock_result = ModImportResult(success=True, templates_added=10)
        mock_importer = MagicMock()
        mock_importer.run = AsyncMock(return_value=mock_result)
        mock_importer_class.return_value = mock_importer

        await run(
            mod_name="TestMod",
            pak_files=[pak_file],
            extract_dir=extract_dir,
            extract_only=True,
        )

        captured = capsys.readouterr()
        assert "Successfully extracted mod 'TestMod'" in captured.out
        assert "Assets extracted: 10" in captured.out
        assert f"Output directory: {extract_dir}" in captured.out


def test_module_importable() -> None:
    """Test that the module can be imported."""
    from fs_tools.commands.add_mod import add_mod  # noqa: F401
