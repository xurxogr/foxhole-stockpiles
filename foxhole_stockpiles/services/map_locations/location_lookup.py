"""Tell the place of the map a stockpile belongs to."""

from collections.abc import Mapping
from typing import Final

from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.services.map_locations.location_table import LOCATIONS, Location

# A hex is wider than tall: its map coordinates go from 0 to 1 over these game units,
# so a distance in them has to be scaled back before comparing.
_HEX_WIDTH: Final[float] = 218400.0
_HEX_HEIGHT: Final[float] = 189000.0
_Y_SCALE: Final[float] = _HEX_HEIGHT / _HEX_WIDTH


def _distance_squared(location: Location, coords: StockpileCoords) -> float:
    """Measure how far a named place is from a stockpile, in the units of the game.

    Args:
        location (Location): The place: its name and map coordinates.
        coords (StockpileCoords): Where the stockpile is.

    Returns:
        float: The squared distance, in units of the width of the hex.
    """
    _, x, y = location
    return (x - coords.x) ** 2 + ((y - coords.y) * _Y_SCALE) ** 2


def location_at(
    hex_code: str | None,
    coords: StockpileCoords | None,
    locations: Mapping[str, tuple[Location, ...]] = LOCATIONS,
) -> str | None:
    """Name the place of a hex a stockpile belongs to, as the game does in a copy.

    The game splits the map of a hex among its named places, towns or not, and gives
    each spot the nearest one.

    Args:
        hex_code (str | None): The code of the hex, such as ``WestgateHex``, in any case.
        coords (StockpileCoords | None): Where the stockpile is on the map of the hex.
        locations (Mapping[str, tuple[Location, ...]]): The named places of each hex,
            by its code in lower case.

    Returns:
        str | None: The name of the place, or None without a hex, coordinates or
            places for the hex.
    """
    if not hex_code or coords is None:
        return None
    candidates = locations.get(hex_code.lower())
    if not candidates:
        return None
    name, _, _ = min(
        candidates, key=lambda location: _distance_squared(location=location, coords=coords)
    )
    return name
