"""Tests for bgr_to_pixmap."""

from typing import Any

import numpy as np

from fs_tools.gui.utils.bgr_pixmap import bgr_to_pixmap


def test_bgr_to_pixmap_keeps_size_and_swaps_channels(qtbot: Any) -> None:
    """The pixmap has the array's size and shows BGR blue as blue.

    Args:
        qtbot: PyQt test fixture.
    """
    image = np.zeros((4, 6, 3), dtype=np.uint8)
    image[:, :, 0] = 255

    pixmap = bgr_to_pixmap(image)

    assert (pixmap.width(), pixmap.height()) == (6, 4)
    color = pixmap.toImage().pixelColor(0, 0)
    assert (color.red(), color.green(), color.blue()) == (0, 0, 255)
