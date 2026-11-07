"""The map locations extracted from the game."""

from pydantic import BaseModel, ConfigDict

from fs_tools.models.map_location_entry import MapLocationEntry


class MapLocations(BaseModel):
    """The named places of the map of every hex, by the code of the hex."""

    hexes: dict[str, list[MapLocationEntry]]

    model_config = ConfigDict(frozen=True, extra="ignore")
