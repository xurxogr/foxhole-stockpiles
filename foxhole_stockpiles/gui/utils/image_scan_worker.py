"""Worker thread for scanning a screenshot directly for the debug viewer."""

import logging
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QThread, Signal

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.sections.ocr import OCRSettings
from foxhole_stockpiles.models.detected_icon_info import DetectedIconInfo
from foxhole_stockpiles.models.scan_result import ScanResult
from foxhole_stockpiles.services.scanner import Scanner

logger = logging.getLogger(__name__)


class ImageScanWorker(QThread):
    """Background thread for scanning a screenshot directly.

    Runs the OCR scanner and, using each item's icon coordinates from the engine,
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
            # Load image
            loaded = cv2.imread(self.image_path)
            if loaded is None:
                self.error.emit(f"Failed to load image: {self.image_path}")
                return
            image: NDArray[np.uint8] = np.asarray(loaded, dtype=np.uint8)

            scanner = Scanner(get_settings().scanner)
            stockpile = scanner.scan_sync(image)

            if not stockpile.items:
                self.error.emit("No stockpile detected in the image")
                return

            # The engine reports each item's icon coordinates directly. The icon
            # box is square; its size scales with the screenshot height relative
            # to the base resolution.
            geometry = OCRSettings()
            scale_factor = image.shape[0] / geometry.height
            box_size = int(geometry.box_height * scale_factor)

            detected_icons: list[DetectedIconInfo] = []
            for i, item in enumerate(stockpile.items):
                if item.x is None or item.y is None:
                    logger.warning("Item %d (%s) has no coordinates; skipping", i, item.code)
                    continue

                icon_x, icon_y = item.x, item.y
                icon_image = image[icon_y : icon_y + box_size, icon_x : icon_x + box_size]

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
                    )
                )

            self.scan_finished.emit(
                ScanResult(
                    stockpile=stockpile,
                    detected_icons=detected_icons,
                    original_image=image,
                )
            )

        except Exception as e:
            logger.exception("Failed to scan image")
            self.error.emit(str(e))
