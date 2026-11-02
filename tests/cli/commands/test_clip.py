"""Tests for the ``fs clip`` command (``foxhole_stockpiles.cli.commands.clip``)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from foxhole_stockpiles.cli.commands import clip

runner = CliRunner()


class TestClipCommand:
    """Test suite for the ``clip`` command via CliRunner."""

    @patch("foxhole_stockpiles.cli.commands.clip.build_clipboard_scan_service")
    @patch("foxhole_stockpiles.cli._settings.setup_logging")
    def test_once_scans_and_exits(
        self,
        mock_setup_logging: MagicMock,
        mock_build_service: MagicMock,
    ) -> None:
        """``--once`` reads the clipboard a single time.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_build_service (MagicMock): Mocked service factory.
        """
        service = MagicMock()
        service.scan_once = AsyncMock(return_value=MagicMock())
        mock_build_service.return_value = service

        result = runner.invoke(clip.app, ["--once"])

        assert result.exit_code == 0
        service.scan_once.assert_awaited_once()

    @patch("foxhole_stockpiles.cli.commands.clip.build_clipboard_scan_service")
    @patch("foxhole_stockpiles.cli._settings.setup_logging")
    def test_once_reports_no_data(
        self,
        mock_setup_logging: MagicMock,
        mock_build_service: MagicMock,
    ) -> None:
        """``--once`` reports when the clipboard holds no stockpile data.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_build_service (MagicMock): Mocked service factory.
        """
        service = MagicMock()
        service.scan_once = AsyncMock(return_value=None)
        mock_build_service.return_value = service

        result = runner.invoke(clip.app, ["--once"])

        assert result.exit_code == 0
        assert "No stockpile data found" in result.stdout

    @patch("foxhole_stockpiles.cli.commands.clip.build_clipboard_scan_service")
    @patch("foxhole_stockpiles.cli._settings.setup_logging")
    def test_missing_catalog_exits_two(
        self,
        mock_setup_logging: MagicMock,
        mock_build_service: MagicMock,
    ) -> None:
        """A missing catalog configuration exits with code 2.

        Args:
            mock_setup_logging (MagicMock): Mocked setup_logging.
            mock_build_service (MagicMock): Mocked service factory.
        """
        mock_build_service.side_effect = ValueError("catalog not configured")

        result = runner.invoke(clip.app, ["--once"])

        assert result.exit_code == 2

    @patch("foxhole_stockpiles.cli.commands.clip.build_clipboard_scan_service")
    @patch("foxhole_stockpiles.cli._settings.setup_logging")
    def test_monitor_mode_primes_and_stops_on_interrupt(
        self,
        mock_setup_logging: MagicMock,
        mock_build_service: MagicMock,
    ) -> None:
        """Monitor mode primes the source and stops on Ctrl+C."""
        service = MagicMock()
        service.poll = AsyncMock(side_effect=KeyboardInterrupt)
        mock_build_service.return_value = service

        result = runner.invoke(clip.app, [])

        assert result.exit_code == 0
        service.prime.assert_called_once()
        assert "Stopping clipboard monitor" in result.stdout

    @patch("foxhole_stockpiles.cli.commands.clip.build_clipboard_scan_service")
    @patch("foxhole_stockpiles.cli._settings.setup_logging")
    def test_output_option_overrides_handlers(
        self,
        mock_setup_logging: MagicMock,
        mock_build_service: MagicMock,
        tmp_path: Path,
    ) -> None:
        """``--output`` builds a file handler overriding configured handlers."""
        service = MagicMock()
        service.scan_once = AsyncMock(return_value=None)
        mock_build_service.return_value = service
        out = tmp_path / "out.json"

        result = runner.invoke(clip.app, ["--once", "--output", str(out)])

        assert result.exit_code == 0
        mock_build_service.assert_called_once()

    @patch(
        "foxhole_stockpiles.cli._settings.get_app_settings",
        side_effect=FileNotFoundError("missing config"),
    )
    def test_config_error_exits_two(self, mock_get_settings: MagicMock) -> None:
        """A bad ``--config`` surfaces as exit code 2."""
        result = runner.invoke(clip.app, ["--once", "--config", "nope.json"])

        assert result.exit_code == 2


@pytest.mark.asyncio
async def test_monitor_survives_a_failed_poll() -> None:
    """One failed clipboard read does not end the monitor."""
    service = MagicMock()
    service.poll = AsyncMock(side_effect=[RuntimeError("clipboard busy"), asyncio.CancelledError()])

    await clip._run(service=service, poll_interval=0, once=False)

    assert service.poll.await_count == 2
