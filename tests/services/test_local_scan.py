"""Tests for the local scan service."""

from unittest.mock import AsyncMock, MagicMock, patch

from foxhole_stockpiles.services.local_scan import LocalScanService


@patch("foxhole_stockpiles.services.local_scan.OutputCoordinator")
@patch("foxhole_stockpiles.services.local_scan.build_scanner")
def test_scan_routes_to_outputs(mock_build_scanner: MagicMock, mock_oc_cls: MagicMock) -> None:
    """scan() scans the image and dispatches the result to the outputs."""
    scanner = MagicMock()
    stockpile = MagicMock()
    scanner.scan_sync.return_value = stockpile
    mock_build_scanner.return_value = scanner

    coordinator = MagicMock()
    coordinator.handle_output = AsyncMock(return_value=None)
    mock_oc_cls.return_value = coordinator

    service = LocalScanService(MagicMock())
    result = service.scan(b"image-bytes")

    assert result is stockpile
    scanner.scan_sync.assert_called_once_with(b"image-bytes", faction=None)
    coordinator.handle_output.assert_awaited_once_with(stockpiles=[stockpile])
