"""Conversion of BGR image arrays into pixmaps Qt can display."""

import numpy as np
from PySide6.QtGui import QImage, QPixmap

from foxhole_stockpiles.core.image_io import swap_rb


def bgr_to_pixmap(image: np.ndarray) -> QPixmap:
    """Convert a BGR image array into a QPixmap.

    Args:
        image (np.ndarray): BGR image array of shape (height, width, 3).

    Returns:
        QPixmap: The image, ready to display.
    """
    rgb = swap_rb(image)
    height, width, channels = rgb.shape
    qt_image = QImage(
        rgb.data.tobytes(),
        width,
        height,
        channels * width,
        QImage.Format.Format_RGB888,
    )
    return QPixmap.fromImage(qt_image)
