"""Naming the place of the map a stockpile belongs to."""

from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.services.map_locations.location_lookup import location_at

_PLACES = {
    "westgatehex": (
        ("Lord's Mouth", 0.829300, 0.430700),
        ("Kingstone", 0.643600, 0.410900),
    )
}


def test_a_spot_takes_the_nearest_place() -> None:
    """Of its own hex."""
    coords = StockpileCoords(x=0.80, y=0.43)

    assert location_at(hex_code="WestgateHex", coords=coords, locations=_PLACES) == "Lord's Mouth"


def test_the_case_of_the_hex_code_does_not_matter() -> None:
    """Saves write DeadLandsHex and the map is named DeadlandsHex."""
    coords = StockpileCoords(x=0.65, y=0.41)

    assert location_at(hex_code="WESTGATEHEX", coords=coords, locations=_PLACES) == "Kingstone"


def test_the_height_of_the_hex_counts_less_than_its_width() -> None:
    """A hex is wider than tall, so the same map distance is shorter upwards."""
    places = {"hex": (("Across", 0.60, 0.50), ("Up", 0.50, 0.611))}

    nearest = location_at(hex_code="hex", coords=StockpileCoords(x=0.5, y=0.5), locations=places)

    assert nearest == "Up"


def test_nothing_is_named_without_what_it_needs() -> None:
    """No hex, no coordinates, or a hex without places."""
    coords = StockpileCoords(x=0.5, y=0.5)

    assert location_at(hex_code=None, coords=coords, locations=_PLACES) is None
    assert location_at(hex_code="WestgateHex", coords=None, locations=_PLACES) is None
    assert location_at(hex_code="AtlantisHex", coords=coords, locations=_PLACES) is None


def test_the_places_of_the_game_name_a_copied_stockpile_as_the_game_does() -> None:
    """A stockpile the game copied as being in Rising Loom, an area, not a town."""
    coords = StockpileCoords(x=0.4577449, y=0.6644695)

    assert location_at(hex_code="TerminusHex", coords=coords) == "Rising Loom"
