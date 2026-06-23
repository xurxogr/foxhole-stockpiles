"""Detected icon information model for debug viewer."""

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from fs_tools.models.debug_candidate import DebugCandidate


class DetectedIconInfo(BaseModel):
    """Information about a detected icon for display in the debug viewer."""

    index: int = Field(description="Position in stockpile")
    code: str = Field(description="Detected item code")
    quantity: int = Field(description="Detected quantity")
    crated: bool = Field(description="Is crated variant")
    confidence: float = Field(description="Match confidence")
    icon_image: NDArray[np.uint8] = Field(description="Extracted icon image (BGR)")
    position: tuple[int, int] = Field(description="(x, y) position in original image")
    size: int = Field(description="Icon size (box_height)")
    candidates: list[DebugCandidate] = Field(
        default_factory=list,
        description="Broad diagnostic candidates from fs_ocr.scan_debug, NCC-ranked",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )
