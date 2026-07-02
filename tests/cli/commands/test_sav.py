"""Tests for the ``fs sav`` command (``foxhole_stockpiles.cli.commands.sav``)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from foxhole_stockpiles.cli.commands import sav

runner = CliRunner()


class TestResolveSaveFile:
    """Test suite for the ``_resolve_save_file`` helper."""

    def test_explicit_file(self, tmp_path: Path) -> None:
        """An explicit, existing file is returned unchanged.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()

        assert sav._resolve_save_file(save_file, None) == save_file

    def test_save_dir_lookup(self, tmp_path: Path) -> None:
        """A save directory is searched for a MapData.sav file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()

        assert sav._resolve_save_file(None, tmp_path) == save_file

    def test_falls_back_to_default_dir(self, tmp_path: Path) -> None:
        """With no file/dir given, the OS default directory is searched."""
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()
        with patch.object(sav, "auto_detect_savefile", return_value=save_file):
            assert sav._resolve_save_file(None, None) == save_file

    def test_no_default_found_exits(self) -> None:
        """No file/dir and no default path exits with an error."""
        with (
            patch.object(sav, "auto_detect_savefile", return_value=None),
            pytest.raises(typer.Exit),
        ):
            sav._resolve_save_file(None, None)


class TestSavCommand:
    """Test suite for the ``sav`` command via CliRunner."""

    def test_no_file_found_exits_one(self, tmp_path: Path) -> None:
        """No discoverable save file exits with code 1.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        result = runner.invoke(sav.app, ["--save-dir", str(tmp_path)])

        assert result.exit_code == 1

    def test_missing_explicit_file_exits_one(self, tmp_path: Path) -> None:
        """An explicit file that does not exist exits with code 1.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        result = runner.invoke(sav.app, ["--file", str(tmp_path / "missing.sav")])

        assert result.exit_code == 1

    @patch("foxhole_stockpiles.cli.commands.sav.SaveFileProcessor")
    @patch("foxhole_stockpiles.cli.commands.sav.OutputCoordinator")
    @patch("foxhole_stockpiles.cli.commands.sav.setup_logging")
    def test_once_processes_and_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_processor_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """``--once`` runs the processor a single time.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_output_coordinator (MagicMock): Mocked OutputCoordinator.
            mock_processor_class (MagicMock): Mocked SaveFileProcessor.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()

        processor = MagicMock()
        processor.run_once = AsyncMock(return_value=None)
        mock_processor_class.return_value = processor

        result = runner.invoke(sav.app, ["--file", str(save_file), "--once"])

        assert result.exit_code == 0
        processor.run_once.assert_awaited_once()

    @patch("foxhole_stockpiles.cli.commands.sav.SaveFileProcessor")
    @patch("foxhole_stockpiles.cli.commands.sav.OutputCoordinator")
    @patch("foxhole_stockpiles.cli.commands.sav.setup_logging")
    def test_watch_mode_runs(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_processor_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Without ``--once`` the processor runs in watch mode."""
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()
        processor = MagicMock()
        processor.run = AsyncMock(return_value=None)
        mock_processor_class.return_value = processor

        result = runner.invoke(sav.app, ["--file", str(save_file)])

        assert result.exit_code == 0
        processor.run.assert_awaited_once()

    @patch("foxhole_stockpiles.cli.commands.sav.SaveFileProcessor")
    @patch("foxhole_stockpiles.cli.commands.sav.OutputCoordinator")
    @patch("foxhole_stockpiles.cli.commands.sav.setup_logging")
    def test_keyboard_interrupt_stops_processor(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_processor_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A KeyboardInterrupt during watch mode stops the processor cleanly."""
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()
        processor = MagicMock()
        processor.run = AsyncMock(side_effect=KeyboardInterrupt)
        mock_processor_class.return_value = processor

        result = runner.invoke(sav.app, ["--file", str(save_file)])

        assert result.exit_code == 0
        processor.stop.assert_called_once()

    @patch("foxhole_stockpiles.cli.commands.sav.SaveFileProcessor")
    @patch("foxhole_stockpiles.cli.commands.sav.OutputCoordinator")
    @patch("foxhole_stockpiles.cli.commands.sav.setup_logging")
    def test_output_option_overrides_handlers(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_processor_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """``--output`` builds a file handler overriding configured handlers."""
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()
        processor = MagicMock()
        processor.run_once = AsyncMock(return_value=None)
        mock_processor_class.return_value = processor

        result = runner.invoke(
            sav.app,
            ["--file", str(save_file), "--once", "--output", str(tmp_path / "out.json")],
        )

        assert result.exit_code == 0
        mock_output_coordinator.assert_called_once()

    @patch(
        "foxhole_stockpiles.cli.commands.sav.get_app_settings",
        side_effect=FileNotFoundError("missing config"),
    )
    def test_config_error_exits_two(self, mock_get_settings: MagicMock, tmp_path: Path) -> None:
        """A bad ``--config`` surfaces as exit code 2."""
        save_file = tmp_path / "World_MapData.sav"
        save_file.touch()

        result = runner.invoke(
            sav.app, ["--file", str(save_file), "--once", "--config", "nope.json"]
        )

        assert result.exit_code == 2
