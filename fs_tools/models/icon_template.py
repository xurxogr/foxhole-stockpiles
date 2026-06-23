"""Icon template model for template matching."""

import fs_ocr
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution


class IconTemplate(BaseModel):
    """Template data for basic icon matching."""

    image: NDArray[np.uint8] = Field(description="Template image as numpy array", exclude=True)
    code: str = Field(description="Item code name", min_length=1)
    crated: bool = Field(description="Whether this is a crated variant", default=False)
    category: ItemCategory = Field(description="Category this template belongs to")
    faction: ItemFaction = Field(description="Faction this template belongs to")
    mod: str = Field(description="Mod this template comes from", min_length=1)
    resolution: SupportedResolution = Field(description="Target resolution for this template")

    # Computed optimization field - calculated automatically on creation
    phash: int = Field(default=0, exclude=True, description="Perceptual hash for fast filtering")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "code": "Rifle",
                "crated": False,
                "resolution": "1080",
                "faction": "neutral",
                "category": "item",
                "mod": "vanilla",
            }
        },
    )

    def model_post_init(self, _context: object) -> None:
        """Automatically compute the perceptual hash after model creation.

        The pHash quickly filters dissimilar templates before NCC matching. It is
        computed by the external ``fs-ocr`` engine so the stored value is exactly
        what the engine compares against at scan time.

        Args:
            _context (object): Pydantic context (unused).
        """
        self.phash = fs_ocr.compute_phash(np.ascontiguousarray(self.image))

    def __str__(self) -> str:
        """String representation of the template."""
        return (
            f"IconTemplate(code={self.code}, crated={self.crated}, faction={self.faction.value}, "
            f"mod={self.mod})"
        )

    def __repr__(self) -> str:
        """Detailed representation of the template."""
        image_shape = self.image.shape if hasattr(self.image, "shape") else "unknown"
        return (
            f"IconTemplate(code='{self.code}', crated={self.crated}, "
            f"mod='{self.mod}', resolution='{self.resolution.value}', "
            f"faction='{self.faction.value}', image_shape={image_shape})"
        )
