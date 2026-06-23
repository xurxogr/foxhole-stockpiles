"""Tests for ImageScanWorker.

The ImageScanWorker is a QThread that runs the OCR scanner in the background and,
using each item's icon coordinates from the engine, derives per-icon overlay
geometry for the debug viewer.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from fs_tools.gui.utils.image_scan_worker import ImageScanWorker
from fs_tools.models.scan_result import ScanResult

# A 1080p image yields a clean icon box size via ICON_BOX_SCALE (= 64/2160):
# box_size = int(64/2160 * 1080) = 32.
IMAGE_HEIGHT = 1080
IMAGE_WIDTH = 1920
EXPECTED_BOX_SIZE = 32


@contextmanager
def _patch_scan(
    image: np.ndarray | None,
    stockpile: Stockpile | None,
) -> Iterator[MagicMock]:
    """Patch read_bgr and the fs-ocr ``scan_debug`` seam used by the worker.

    The worker scans via ``fs_ocr.StockpileScanner.scan_debug`` and adapts the
    raw result with ``to_runtime_stockpile``. To keep existing tests expressed in
    terms of a runtime ``Stockpile``, this mirrors that stockpile's items as mock
    fs-ocr items (carrying empty ``debug_candidates``) and makes the adapter
    return the runtime stockpile unchanged.

    Args:
        image (np.ndarray | None): Image returned by read_bgr (None simulates a
            load failure).
        stockpile (Stockpile | None): Runtime stockpile the scan should yield.

    Yields:
        MagicMock: The mock fs-ocr scanner instance.
    """
    module = "fs_tools.gui.utils.image_scan_worker"

    fs_items: list[MagicMock] = []
    if stockpile is not None:
        for item in stockpile.items:
            fs_item = MagicMock()
            fs_item.code = item.code
            fs_item.quantity = item.quantity
            fs_item.crated = item.crated
            fs_item.confidence = item.confidence
            fs_item.x = item.x
            fs_item.y = item.y
            fs_item.debug_candidates = []
            fs_items.append(fs_item)

    fs_result = MagicMock()
    fs_result.items = fs_items
    mock_scanner = MagicMock()
    mock_scanner.scan_debug.return_value = fs_result

    with (
        patch(f"{module}.read_bgr", return_value=image),
        patch(f"{module}.fs_ocr.StockpileScanner", return_value=mock_scanner),
        patch(f"{module}.fs_ocr.ScanConfig"),
        patch(f"{module}.to_runtime_stockpile", return_value=stockpile),
    ):
        yield mock_scanner


@pytest.fixture
def worker(tmp_path: Path) -> ImageScanWorker:
    """Create an ImageScanWorker instance.

    Args:
        tmp_path (Path): Temporary directory path.

    Returns:
        ImageScanWorker: Worker instance.
    """
    image_path = tmp_path / "screenshot.png"
    database_path = tmp_path / "database.h5"

    return ImageScanWorker(str(image_path), database_path)


@pytest.fixture
def sample_image() -> np.ndarray:
    """Create a 1080p BGR image.

    Returns:
        np.ndarray: A zeroed BGR image of size IMAGE_HEIGHT x IMAGE_WIDTH.
    """
    return np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)


@pytest.fixture
def mock_stockpile_item() -> StockpileItem:
    """Create a mock stockpile item with icon coordinates.

    Returns:
        StockpileItem: A mock stockpile item.
    """
    return StockpileItem(code="TestItem", quantity=100, crated=False, confidence=0.95, x=150, y=200)


@pytest.fixture
def mock_stockpile(mock_stockpile_item: StockpileItem) -> Stockpile:
    """Create a mock stockpile.

    Args:
        mock_stockpile_item (StockpileItem): Mock stockpile item.

    Returns:
        Stockpile: A mock stockpile.
    """
    return Stockpile(
        name="Test Stockpile",
        type=StockpileType.STORAGE_DEPOT,
        resolution="1920x1080",
        items=[mock_stockpile_item],
    )


class TestImageScanWorkerInitialization:
    """Tests for ImageScanWorker initialization."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test ImageScanWorker initialization.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        image_path = tmp_path / "screenshot.png"
        database_path = tmp_path / "database.h5"

        worker = ImageScanWorker(str(image_path), database_path)

        assert worker.image_path == str(image_path)
        assert worker.database_path == database_path

    def test_signals_exist(self, worker: ImageScanWorker) -> None:
        """Test that required signals exist.

        Args:
            worker (ImageScanWorker): Worker instance.
        """
        assert hasattr(worker, "scan_finished")
        assert hasattr(worker, "error")


class TestImageScanWorkerRun:
    """Tests for ImageScanWorker run method."""

    def test_run_image_load_failure(self, worker: ImageScanWorker) -> None:
        """Test run with failed image load.

        Args:
            worker (ImageScanWorker): Worker instance.
        """
        mock_error = MagicMock()

        with patch.object(worker, "error", mock_error):
            with _patch_scan(image=None, stockpile=None):
                worker.run()

        mock_error.emit.assert_called_once()
        assert "Failed to load image" in mock_error.emit.call_args[0][0]

    def test_run_no_stockpile_detected(
        self, worker: ImageScanWorker, sample_image: np.ndarray
    ) -> None:
        """Test run when the scan returns no items.

        Args:
            worker (ImageScanWorker): Worker instance.
            sample_image (np.ndarray): Sample image.
        """
        empty_stockpile = Stockpile(
            name="", type=StockpileType.UNDEFINED, resolution="1920x1080", items=[]
        )
        mock_error = MagicMock()

        with patch.object(worker, "error", mock_error):
            with _patch_scan(image=sample_image, stockpile=empty_stockpile):
                worker.run()

        mock_error.emit.assert_called_once()
        assert "No stockpile detected" in mock_error.emit.call_args[0][0]

    def test_run_success(
        self, worker: ImageScanWorker, sample_image: np.ndarray, mock_stockpile: Stockpile
    ) -> None:
        """Test successful scan execution.

        Args:
            worker (ImageScanWorker): Worker instance.
            sample_image (np.ndarray): Sample image.
            mock_stockpile (Stockpile): Mock stockpile.
        """
        mock_finished = MagicMock()

        with patch.object(worker, "scan_finished", mock_finished):
            with _patch_scan(image=sample_image, stockpile=mock_stockpile):
                worker.run()

        mock_finished.emit.assert_called_once()
        result = mock_finished.emit.call_args[0][0]
        assert isinstance(result, ScanResult)
        assert result.stockpile == mock_stockpile
        assert len(result.detected_icons) == 1

    def test_run_success_detected_icon_info(
        self, worker: ImageScanWorker, sample_image: np.ndarray, mock_stockpile: Stockpile
    ) -> None:
        """Test detected icon info uses the item's coordinates and scaled box size.

        Args:
            worker (ImageScanWorker): Worker instance.
            sample_image (np.ndarray): Sample image.
            mock_stockpile (Stockpile): Mock stockpile (item at x=150, y=200).
        """
        mock_finished = MagicMock()

        with patch.object(worker, "scan_finished", mock_finished):
            with _patch_scan(image=sample_image, stockpile=mock_stockpile):
                worker.run()

        result = mock_finished.emit.call_args[0][0]
        icon_info = result.detected_icons[0]

        assert icon_info.index == 0
        assert icon_info.code == "TestItem"
        assert icon_info.quantity == 100
        assert icon_info.crated is False
        assert icon_info.confidence == 0.95
        # Position comes straight from the item's coordinates.
        assert icon_info.position == (150, 200)
        assert icon_info.size == EXPECTED_BOX_SIZE

    def test_run_exception_handling(self, worker: ImageScanWorker) -> None:
        """Test run handles exceptions.

        Args:
            worker (ImageScanWorker): Worker instance.
        """
        mock_error = MagicMock()
        module = "fs_tools.gui.utils.image_scan_worker"

        with patch.object(worker, "error", mock_error):
            with patch(f"{module}.read_bgr", side_effect=Exception("Unexpected error")):
                worker.run()

        mock_error.emit.assert_called_once()
        assert "Unexpected error" in mock_error.emit.call_args[0][0]

    def test_run_skips_item_without_coordinates(
        self, worker: ImageScanWorker, sample_image: np.ndarray
    ) -> None:
        """Test run skips items that have no coordinates.

        Args:
            worker (ImageScanWorker): Worker instance.
            sample_image (np.ndarray): Sample image.
        """
        stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            resolution="1920x1080",
            items=[
                StockpileItem(code="WithCoords", quantity=10, x=100, y=120),
                StockpileItem(code="NoCoords", quantity=20),  # x/y default to None
            ],
        )
        mock_finished = MagicMock()

        with patch.object(worker, "scan_finished", mock_finished):
            with _patch_scan(image=sample_image, stockpile=stockpile):
                worker.run()

        mock_finished.emit.assert_called_once()
        result = mock_finished.emit.call_args[0][0]
        # Only the item with coordinates produces an overlay icon.
        assert len(result.detected_icons) == 1
        assert result.detected_icons[0].code == "WithCoords"

    def test_run_crated_item(self, worker: ImageScanWorker, sample_image: np.ndarray) -> None:
        """Test run with a crated item.

        Args:
            worker (ImageScanWorker): Worker instance.
            sample_image (np.ndarray): Sample image.
        """
        crated_stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            resolution="1920x1080",
            items=[
                StockpileItem(
                    code="CratedItem", quantity=5, crated=True, confidence=0.88, x=100, y=100
                )
            ],
        )
        mock_finished = MagicMock()

        with patch.object(worker, "scan_finished", mock_finished):
            with _patch_scan(image=sample_image, stockpile=crated_stockpile):
                worker.run()

        icon_info = mock_finished.emit.call_args[0][0].detected_icons[0]
        assert icon_info.crated is True
        assert icon_info.quantity == 5

    def test_run_item_with_none_confidence(
        self, worker: ImageScanWorker, sample_image: np.ndarray
    ) -> None:
        """Test run with an item that has None confidence.

        Args:
            worker (ImageScanWorker): Worker instance.
            sample_image (np.ndarray): Sample image.
        """
        stockpile = Stockpile(
            name="Test",
            type=StockpileType.STORAGE_DEPOT,
            resolution="1920x1080",
            items=[
                StockpileItem(
                    code="TestItem", quantity=100, crated=False, confidence=None, x=100, y=100
                )
            ],
        )
        mock_finished = MagicMock()

        with patch.object(worker, "scan_finished", mock_finished):
            with _patch_scan(image=sample_image, stockpile=stockpile):
                worker.run()

        icon_info = mock_finished.emit.call_args[0][0].detected_icons[0]
        # None confidence should default to 0.0
        assert icon_info.confidence == 0.0


class TestImageScanWorkerSignals:
    """Tests for ImageScanWorker signals."""

    def test_finished_signal_type(self, worker: ImageScanWorker) -> None:
        """Test that finished signal is properly defined.

        Args:
            worker (ImageScanWorker): Worker instance.
        """
        results: list[Any] = []
        worker.scan_finished.connect(lambda x: results.append(x))

        test_obj = {"test": "data"}
        worker.scan_finished.emit(test_obj)

        assert len(results) == 1
        assert results[0] == test_obj

    def test_error_signal_type(self, worker: ImageScanWorker) -> None:
        """Test that error signal is properly defined.

        Args:
            worker (ImageScanWorker): Worker instance.
        """
        errors: list[str] = []
        worker.error.connect(lambda x: errors.append(x))

        worker.error.emit("Test error")

        assert len(errors) == 1
        assert errors[0] == "Test error"
