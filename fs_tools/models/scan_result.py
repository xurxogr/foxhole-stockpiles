"""Scan result model for debug viewer."""

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.models.stockpile import Stockpile
from fs_tools.models.detected_icon_info import DetectedIconInfo


class ScanResult(BaseModel):
    """Result from image scan for debug viewer."""

    stockpile: Stockpile = Field(description="Scanned stockpile data")
    detected_icons: list[DetectedIconInfo] = Field(description="List of detected icon info")
    original_image: NDArray[np.uint8] = Field(description="Original screenshot image (BGR)")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )
