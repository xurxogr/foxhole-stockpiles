"""Tests for the one-shot SAV scan worker."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QThread

from foxhole_stockpiles.gui.utils.sav_scan_worker import SavScanWorker
from foxhole_stockpiles.models.stockpile import Stockpile


class TestSavScanWorker:
    """Tests for SavScanWorker."""

    def test_initialization(self) -> None:
        """Test SavScanWorker initialization."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        worker = SavScanWorker(sav_path, output_coordinator)

        assert worker._sav_path == sav_path
        assert worker._output_coordinator == output_coordinator
        assert isinstance(worker, QThread)

    def test_run_success(self) -> None:
        """Test successful SAV scan."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        mock_stockpiles = [MagicMock(spec=Stockpile)]

        with (
            patch(
                "foxhole_stockpiles.gui.utils.sav_scan_worker.SaveFileProcessor"
            ) as mock_processor_class,
            patch("foxhole_stockpiles.gui.utils.sav_scan_worker.asyncio.run") as mock_asyncio_run,
        ):
            mock_asyncio_run.return_value = mock_stockpiles

            worker = SavScanWorker(sav_path, output_coordinator)

            # Collect emitted signals
            finished_spy: list[bool] = []
            stockpiles_spy: list[Any] = []
            worker.scan_finished.connect(lambda success: finished_spy.append(success))
            worker.stockpiles_found.connect(lambda s: stockpiles_spy.append(s))

            # Run the worker directly (not in thread for testing)
            worker.run()

            # Verify processor was created with correct arguments
            mock_processor_class.assert_called_once_with(
                file_path=sav_path,
                output_coordinator=output_coordinator,
                emit_all_on_start=True,
            )

            # Verify asyncio.run was called
            mock_asyncio_run.assert_called_once()

            # Verify signals
            assert len(stockpiles_spy) == 1
            assert stockpiles_spy[0] == mock_stockpiles
            assert len(finished_spy) == 1
            assert finished_spy[0] is True

    def test_run_runtime_error(self) -> None:
        """Test SAV scan with runtime error."""
        sav_path = Path("/nonexistent/file.sav")
        output_coordinator = MagicMock()

        with patch(
            "foxhole_stockpiles.gui.utils.sav_scan_worker.SaveFileProcessor",
            side_effect=RuntimeError("Parse failed"),
        ):
            worker = SavScanWorker(sav_path, output_coordinator)

            error_spy: list[str] = []
            finished_spy: list[bool] = []
            worker.error.connect(lambda msg: error_spy.append(msg))
            worker.scan_finished.connect(lambda success: finished_spy.append(success))

            worker.run()

            assert len(error_spy) == 1
            assert "Parse failed" in error_spy[0]
            assert len(finished_spy) == 1
            assert finished_spy[0] is False

    def test_run_generic_exception(self) -> None:
        """Test SAV scan with generic exception."""
        sav_path = Path("/test/file.sav")
        output_coordinator = MagicMock()

        with patch(
            "foxhole_stockpiles.gui.utils.sav_scan_worker.SaveFileProcessor",
            side_effect=ValueError("Unexpected error"),
        ):
            worker = SavScanWorker(sav_path, output_coordinator)

            error_spy: list[str] = []
            finished_spy: list[bool] = []
            worker.error.connect(lambda msg: error_spy.append(msg))
            worker.scan_finished.connect(lambda success: finished_spy.append(success))

            worker.run()

            assert len(error_spy) == 1
            assert "Error processing SAV file" in error_spy[0]
            assert "Unexpected error" in error_spy[0]
            assert len(finished_spy) == 1
            assert finished_spy[0] is False
