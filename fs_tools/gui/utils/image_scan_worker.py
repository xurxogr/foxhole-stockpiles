"""Worker thread for scanning a screenshot directly for the debug viewer."""

import logging
from pathlib import Path

import fs_ocr
import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.core.image_io import read_bgr
from foxhole_stockpiles.services.scanner import to_runtime_stockpile
from fs_tools.constants import ICON_BOX_SCALE
from fs_tools.models.debug_candidate import DebugCandidate
from fs_tools.models.detected_icon_info import DetectedIconInfo
from fs_tools.models.scan_result import ScanResult

logger = logging.getLogger(__name__)

# Scan with the widest reasonable matching window so a single scan yields every
# candidate the viewer might want; the viewer then filters client-side by the
# user's pHash-threshold / max-NCC controls (each candidate carries its own
# phash_distance), so changing those never needs a re-scan.
_DEBUG_PHASH_THRESHOLD = 64
_DEBUG_MAX_NCC_CANDIDATES = 100


class ImageScanWorker(QThread):
    """Background thread that scans a screenshot via fs-ocr's debug scan.

    Runs ``fs_ocr.StockpileScanner.scan_debug`` so each detected item carries
    the engine's full diagnostic candidate set (``debug_candidates``), and
    derives per-icon position/size info for the debug viewer's overlay. The icon
    box size is a constant scaled from the screenshot resolution.

    Note: the result signal is named ``scan_finished`` (not ``finished``) to avoid
    shadowing ``QThread``'s built-in ``finished`` signal, which would cause
    connected slots to fire twice.
    """

    scan_finished = Signal(object)  # ScanResult
    error = Signal(str)

    def __init__(self, image_path: str, database_path: Path) -> None:
        """Initialize the image scan worker.

        Args:
            image_path (str): Path to the screenshot file to scan.
            database_path (Path): Path to the template database file.
        """
        super().__init__()
        self.image_path = image_path
        self.database_path = database_path

    def run(self) -> None:
        """Run the scan in a background thread.

        Emits:
            scan_finished: Signal with ScanResult on success.
            error: Signal with error message on failure.
        """
        try:
            loaded = read_bgr(self.image_path)
            if loaded is None:
                self.error.emit(f"Failed to load image: {self.image_path}")
                return
            image: NDArray[np.uint8] = loaded

            scanner = fs_ocr.StockpileScanner(database_path=str(self.database_path))
            config = fs_ocr.ScanConfig(
                phash_threshold=_DEBUG_PHASH_THRESHOLD,
                max_ncc_candidates=_DEBUG_MAX_NCC_CANDIDATES,
            )
            result = scanner.scan_debug(image, None, config)

            if not result.items:
                self.error.emit("No stockpile detected in the image")
                return

            # The engine reports each item's icon coordinates directly. The icon
            # box is square; its size scales with the screenshot height relative
            # to the base resolution.
            box_size = int(ICON_BOX_SCALE * image.shape[0])

            detected_icons: list[DetectedIconInfo] = []
            for i, item in enumerate(result.items):
                if item.x is None or item.y is None:
                    logger.warning("Item %d (%s) has no coordinates; skipping", i, item.code)
                    continue

                icon_x, icon_y = item.x, item.y
                icon_image = image[icon_y : icon_y + box_size, icon_x : icon_x + box_size]

                candidates = [
                    DebugCandidate(
                        code=c.code,
                        mod=c.mod,
                        category=str(c.category),
                        crated=c.crated,
                        faction=str(c.faction),
                        confidence=c.confidence,
                        phash_distance=c.phash_distance,
                    )
                    for c in (item.debug_candidates or [])
                ]

                detected_icons.append(
                    DetectedIconInfo(
                        index=i,
                        code=item.code,
                        quantity=item.quantity,
                        crated=item.crated,
                        confidence=item.confidence or 0.0,
                        icon_image=icon_image,
                        position=(icon_x, icon_y),
                        size=box_size,
                        candidates=candidates,
                    )
                )

            self.scan_finished.emit(
                ScanResult(
                    stockpile=to_runtime_stockpile(result),
                    detected_icons=detected_icons,
                    original_image=image,
                )
            )

        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            logger.exception("Failed to scan image")
            self.error.emit(str(e))
