"""What importing the map locations changed."""

from pydantic import BaseModel, ConfigDict


class MapLocationsReport(BaseModel):
    """The result of importing the named places of each hex."""

    hexes: int
    locations: int
    not_in_enum: list[str]

    model_config = ConfigDict(frozen=True)
