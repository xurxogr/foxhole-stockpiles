"""One place of a hex in the map locations extracted from the game."""

from pydantic import BaseModel, ConfigDict, Field


class MapLocationEntry(BaseModel):
    """A named place of the map of a hex, as fs-assets extracts it from the game."""

    name: str = Field(min_length=1)
    major: bool
    # Coordinates on the map of the hex; a few places lie past its edge.
    x: float
    y: float

    model_config = ConfigDict(frozen=True, extra="ignore")
