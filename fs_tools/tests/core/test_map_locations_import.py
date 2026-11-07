"""Copying the named places of the map of each hex from the game into the application."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from fs_tools.core.map_locations_import import import_map_locations, read_locations


def _place(name: str, x: float = 0.5, y: float = 0.5, major: bool = False) -> dict[str, Any]:
    return {"name": name, "major": major, "x": x, "y": y}


def _write(path: Path, hexes: dict[str, list[dict[str, Any]]]) -> Path:
    path.write_text(json.dumps({"hexes": hexes}), encoding="utf-8")
    return path


def test_towns_and_areas_are_all_kept_in_order(tmp_path: Path) -> None:
    """The game names a spot after the nearest of any of them."""
    source = _write(
        tmp_path / "locations.json",
        {"WestgateHex": [_place("Kingstone", major=True), _place("Cattle March")]},
    )

    places = read_locations(source)

    assert [entry.name for entry in places["WestgateHex"]] == ["Cattle March", "Kingstone"]


def test_a_hex_without_places_is_refused(tmp_path: Path) -> None:
    """Every hex of the game has some."""
    source = _write(tmp_path / "locations.json", {"WestgateHex": [], "AcrithiaHex": []})

    with pytest.raises(ValueError, match="AcrithiaHex, WestgateHex"):
        read_locations(source)


def test_another_file_is_refused(tmp_path: Path) -> None:
    """Such as the display names."""
    source = tmp_path / "names.json"
    source.write_text(json.dumps([{"CodeName": "Seaport"}]), encoding="utf-8")

    with pytest.raises(ValidationError):
        read_locations(source)


def test_the_module_written_holds_every_place(tmp_path: Path) -> None:
    """By the code of its hex in lower case, ready to import."""
    source = _write(
        tmp_path / "locations.json",
        {
            "DeadlandsHex": [_place('The "Quote"', x=0.25, y=1.04)],
            "AtlantisHex": [_place("Lord's Mouth", x=0.8293, y=0.4307, major=True)],
        },
    )
    output = tmp_path / "location_table.py"

    report = import_map_locations(map_locations=source, output=output)

    namespace: dict[str, Any] = {}
    exec(compile(output.read_text(encoding="utf-8"), str(output), "exec"), namespace)  # noqa: S102
    assert namespace["LOCATIONS"] == {
        "atlantishex": (("Lord's Mouth", 0.8293, 0.4307),),
        "deadlandshex": (('The "Quote"', 0.25, 1.04),),
    }
    assert report.hexes == 2
    assert report.locations == 2
    assert report.not_in_enum == ["AtlantisHex"]
