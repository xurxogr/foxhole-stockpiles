"""Debug candidate model for the debug image viewer.

Mirrors ``fs_ocr.DebugCandidate``: one template that passed the icon's pHash
threshold (any code/category/mod/faction, matching crated state), NCC-scored by
the engine. The viewer matches it back to a DB template (by code/mod/crated/
faction) to display the template image.
"""

from pydantic import BaseModel, ConfigDict, Field


class DebugCandidate(BaseModel):
    """A diagnostic match candidate produced by ``fs_ocr.scan_debug``."""

    code: str = Field(description="Candidate item code")
    mod: str = Field(description="Mod the candidate template belongs to")
    category: str = Field(description="Item category value")
    crated: bool = Field(description="Crated variant")
    faction: str = Field(description="Item faction value")
    confidence: float = Field(description="NCC score (TM_CCOEFF_NORMED)")
    phash_distance: int = Field(description="Hamming distance between icon and template pHash")

    model_config = ConfigDict(extra="forbid")
