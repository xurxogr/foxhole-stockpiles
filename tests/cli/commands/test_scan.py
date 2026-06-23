"""Tests for the ``fs scan`` command (``foxhole_stockpiles.cli.commands.scan``)."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from typer.testing import CliRunner

from foxhole_stockpiles.cli._settings import get_app_settings
from foxhole_stockpiles.cli.commands import scan
from foxhole_stockpiles.core.settings.sections.output import FileHandlerSettings
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.output_destination import OutputDestination

runner = CliRunner()


@pytest.fixture
def mock_stockpile() -> MagicMock:
    """Create a mock stockpile for testing.

    Returns:
        MagicMock: Configured mock Stockpile instance.
    """
    stockpile = MagicMock()
    stockpile.items = []
    stockpile.resolution = "1080"
    stockpile.faction = ItemFaction.NEUTRAL
    return stockpile


class TestGetAppSettings:
    """Test suite for the ``get_app_settings`` helper."""

    def test_default_settings(self) -> None:
        """Returns default settings when no config file is given."""
        settings = get_app_settings(config_file=None)

        assert settings is not None
        assert hasattr(settings, "scanner")
        assert hasattr(settings, "logging")

    def test_settings_from_config_file(self, tmp_path: Path) -> None:
        """Loads and applies values from a custom JSON config file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        config_file = tmp_path / "config.json"
        config_file.write_text('{"logging": {"log_level": "CRITICAL"}}')

        settings = get_app_settings(config_file=str(config_file))

        assert settings.logging.log_level == "CRITICAL"

    def test_missing_config_file_raises(self, tmp_path: Path) -> None:
        """A missing config file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        with pytest.raises(FileNotFoundError):
            get_app_settings(config_file=str(tmp_path / "nope.json"))

    def test_invalid_json_config_raises(self, tmp_path: Path) -> None:
        """An invalid JSON config file raises ValueError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ not json")

        with pytest.raises(ValueError):
            get_app_settings(config_file=str(config_file))


class TestCreateHandlerConfig:
    """Test suite for ``_create_handler_config_for_destination``."""

    def test_file_destination_uses_output_path(self, tmp_path: Path) -> None:
        """File destination uses the supplied output path.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        output_file = tmp_path / "out.json"
        config = scan._create_handler_config_for_destination(OutputDestination.FILE, output_file)

        assert isinstance(config.handler, FileHandlerSettings)
        assert config.handler.path == str(output_file)

    def test_console_destination(self) -> None:
        """Console destination produces a console handler config."""
        config = scan._create_handler_config_for_destination(OutputDestination.CONSOLE)

        assert config is not None

    def test_return_destination_default(self) -> None:
        """Return destination produces a return handler config."""
        config = scan._create_handler_config_for_destination(OutputDestination.RETURN)

        assert config is not None


@patch("foxhole_stockpiles.cli.commands.scan.read_bgr")
@patch("foxhole_stockpiles.cli.commands.scan.Scanner")
@patch("foxhole_stockpiles.cli.commands.scan.OutputCoordinator")
@patch("foxhole_stockpiles.cli.commands.scan.setup_logging")
class TestScanCommand:
    """Test suite for the ``scan`` command via CliRunner."""

    def test_basic_scan(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_scanner_class: MagicMock,
        mock_imread: MagicMock,
        mock_stockpile: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A basic scan loads the image and runs the pipeline.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_output_coordinator (MagicMock): Mocked OutputCoordinator.
            mock_scanner_class (MagicMock): Mocked Scanner.
            mock_imread (MagicMock): Mocked read_bgr.
            mock_stockpile (MagicMock): Mock stockpile fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "db.h5"
        database_path.touch()

        mock_imread.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)

        coordinator = MagicMock()
        coordinator.scan = AsyncMock(return_value=mock_stockpile)
        mock_scanner_class.return_value = coordinator

        handler = MagicMock()
        handler.handle_output = AsyncMock(return_value=None)
        mock_output_coordinator.return_value = handler

        result = runner.invoke(
            scan.app,
            ["--image", str(image_path), "--database", str(database_path)],
        )

        assert result.exit_code == 0
        mock_imread.assert_called_once()
        coordinator.scan.assert_awaited_once()
        handler.handle_output.assert_awaited_once()

    def test_faction_filter(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_scanner_class: MagicMock,
        mock_imread: MagicMock,
        mock_stockpile: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The ``--faction`` flag is forwarded to the coordinator.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_output_coordinator (MagicMock): Mocked OutputCoordinator.
            mock_scanner_class (MagicMock): Mocked Scanner.
            mock_imread (MagicMock): Mocked read_bgr.
            mock_stockpile (MagicMock): Mock stockpile fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "db.h5"
        database_path.touch()

        mock_imread.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)

        coordinator = MagicMock()
        coordinator.scan = AsyncMock(return_value=mock_stockpile)
        mock_scanner_class.return_value = coordinator

        handler = MagicMock()
        handler.handle_output = AsyncMock(return_value={"items": []})
        mock_output_coordinator.return_value = handler

        result = runner.invoke(
            scan.app,
            [
                "--image",
                str(image_path),
                "--database",
                str(database_path),
                "--faction",
                "w",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = coordinator.scan.call_args.kwargs
        assert call_kwargs["faction"] == ItemFaction.WARDENS

    def test_token_forwarded_to_output(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_scanner_class: MagicMock,
        mock_imread: MagicMock,
        mock_stockpile: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The ``--token`` flag is forwarded to the output coordinator.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_output_coordinator (MagicMock): Mocked OutputCoordinator.
            mock_scanner_class (MagicMock): Mocked Scanner.
            mock_imread (MagicMock): Mocked read_bgr.
            mock_stockpile (MagicMock): Mock stockpile fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "db.h5"
        database_path.touch()

        mock_imread.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)

        coordinator = MagicMock()
        coordinator.scan = AsyncMock(return_value=mock_stockpile)
        mock_scanner_class.return_value = coordinator

        handler = MagicMock()
        handler.handle_output = AsyncMock(return_value=None)
        mock_output_coordinator.return_value = handler

        result = runner.invoke(
            scan.app,
            [
                "--image",
                str(image_path),
                "--database",
                str(database_path),
                "--token",
                "abc123",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = handler.handle_output.call_args.kwargs
        assert call_kwargs.get("token") == "abc123"

    def test_image_load_failure(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_scanner_class: MagicMock,
        mock_imread: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A failed image load exits with code 1.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_output_coordinator (MagicMock): Mocked OutputCoordinator.
            mock_scanner_class (MagicMock): Mocked Scanner.
            mock_imread (MagicMock): Mocked read_bgr.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "db.h5"
        database_path.touch()

        mock_imread.return_value = None

        result = runner.invoke(
            scan.app,
            ["--image", str(image_path), "--database", str(database_path)],
        )

        assert result.exit_code == 1

    def test_pipeline_error_exits_one(
        self,
        mock_setup_logging: MagicMock,
        mock_output_coordinator: MagicMock,
        mock_scanner_class: MagicMock,
        mock_imread: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A pipeline error exits with code 1.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_output_coordinator (MagicMock): Mocked OutputCoordinator.
            mock_scanner_class (MagicMock): Mocked Scanner.
            mock_imread (MagicMock): Mocked read_bgr.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "db.h5"
        database_path.touch()

        mock_imread.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)

        coordinator = MagicMock()

        async def boom(*args: Any, **kwargs: Any) -> None:
            raise ValueError("processing error")

        coordinator.scan = boom
        mock_scanner_class.return_value = coordinator

        result = runner.invoke(
            scan.app,
            ["--image", str(image_path), "--database", str(database_path)],
        )

        assert result.exit_code == 1


class TestScanDatabaseValidation:
    """Test suite for database-path validation (no pipeline mocking needed)."""

    def test_missing_database_exits_two(self, tmp_path: Path) -> None:
        """A missing database (and none in config) exits with code 2.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()

        mock_settings = MagicMock()
        mock_settings.scanner.database_path = None

        with patch(
            "foxhole_stockpiles.cli._settings.get_settings",
            return_value=mock_settings,
        ):
            result = runner.invoke(scan.app, ["--image", str(image_path)])

        assert result.exit_code == 2

    def test_database_file_not_found_exits_one(self, tmp_path: Path) -> None:
        """A non-existent database file exits with code 1.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "missing.h5"

        result = runner.invoke(
            scan.app,
            ["--image", str(image_path), "--database", str(database_path)],
        )

        assert result.exit_code == 1

    def test_database_path_is_directory_exits_one(self, tmp_path: Path) -> None:
        """A database path pointing at a directory exits with code 1.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        image_path = tmp_path / "shot.png"
        image_path.touch()
        database_path = tmp_path / "db_dir"
        database_path.mkdir()

        result = runner.invoke(
            scan.app,
            ["--image", str(image_path), "--database", str(database_path)],
        )

        assert result.exit_code == 1
