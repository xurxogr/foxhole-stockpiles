"""Icon template model for template matching."""

import cv2
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
        """Automatically compute perceptual hash after model creation.

        The perceptual hash (pHash) is used to quickly filter out dissimilar templates
        before running the more expensive OpenCV template matching.

        Args:
            _context (object): Pydantic context (unused).
        """
        # Convert to grayscale for hash computation
        img_gray = np.asarray(cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY), dtype=np.uint8)

        # Compute perceptual hash
        self._compute_phash(img_gray)

    def _compute_phash(self, img_gray: NDArray[np.uint8]) -> None:
        """Compute perceptual hash efficiently using vectorized operations."""
        # Resize to 8x8 for standard pHash - use INTER_AREA for better downsampling
        img_8x8 = cv2.resize(img_gray, (8, 8), interpolation=cv2.INTER_AREA)

        # Compute average once
        avg = img_8x8.mean()

        # Vectorized binary comparison and hash computation
        bits = (img_8x8 > avg).astype(np.uint8)

        # Efficient bit packing using numpy's dot product with powers of 2
        powers = np.power(2, np.arange(63, -1, -1, dtype=np.uint64))
        self.phash = int(np.dot(bits.flatten(), powers))

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
