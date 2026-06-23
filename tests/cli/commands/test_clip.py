"""Tests for the ``fs clip`` command (``foxhole_stockpiles.cli.commands.clip``)."""

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from foxhole_stockpiles.cli.commands import clip

runner = CliRunner()


class TestClipCommand:
    """Test suite for the ``clip`` command via CliRunner."""

    @patch("foxhole_stockpiles.cli.commands.clip.build_clipboard_scan_service")
    @patch("foxhole_stockpiles.cli.commands.clip.setup_logging")
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
    @patch("foxhole_stockpiles.cli.commands.clip.setup_logging")
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
    @patch("foxhole_stockpiles.cli.commands.clip.setup_logging")
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
