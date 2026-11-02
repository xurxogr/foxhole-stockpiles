#!/usr/bin/env python3
"""List stockpile type names and their translations from the game's PAK.

Reads the blueprints and ``.locres`` files directly from the PAK with
``fs-assets``. Each ``StockpileType`` is matched to its blueprint by CodeName,
which is what the enum values hold.

It can also report structures that look like player-accessible stockpiles but
aren't a known type, to spot new ones after a game update.

Usage:
    python tools/sync_stockpile_translations.py [--pak PATH] [--show-guids] [--discover]

Options:
    --pak PATH      Game PAK (default: War-WindowsNoEditor.pak in the Steam install)
    --show-guids    Show the text GUID of each stockpile type
    --discover      Report structures that aren't a known stockpile type
"""

import argparse
import json
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import fs_assets

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from foxhole_stockpiles.enums.stockpile_type import StockpileType  # noqa: E402

PAK_NAME = "War-WindowsNoEditor.pak"
LOCALIZATION_IN_PAK = "War/Content/Localization"
BLUEPRINTS_IN_PAK = "War/Content/Blueprints"

# Patterns that indicate player-accessible stockpile structures
STOCKPILE_INDICATORS = {
    "storage_facility": "ESimScreen::StorageFacility",
    "base_stockpile": "spawn and stockpile",
    "item_stockpile": "GenericItemStockpileComponent",
    "generic_stockpile": "GenericStockpileComponent",
    "static_base": "ESpawnPointCategory::StaticBase",
}

# Patterns to exclude from discovery (not player-accessible stockpiles)
EXCLUDE_PATTERNS = [
    "Transfer",  # Transfer stations
    "Destroyed",  # Destroyed versions
    "BuildSite",  # Build sites
    "Factory",  # Factories (internal stockpiles)
    "Mine",  # Mines (internal stockpiles)
    "Refinery",  # Refineries (internal stockpiles)
    "Harvester",  # Harvesters (internal stockpiles)
    "Room",  # Bunker rooms (internal stockpiles)
    "Engine",  # Engine rooms
    "Hospital",  # Hospitals
    "Container",  # Containers
    "Pallet",  # Pallets
    "Platform",  # Platforms
    "Tunnel",  # Tunnels
    "Mixer",  # Concrete mixer
    "Equipment",  # Construction equipment
    "Power",  # Power plants
    "Pump",  # Water pumps
    "Well",  # Oil wells
    "Offshore",  # Offshore platforms
    "Dock",  # Dry dock
    "Assembly",  # Assembly stations
    "Modification",  # Modification center
    "Trailer",  # Trailers
]


class Blueprint(NamedTuple):
    """The fields of a game blueprint this tool reads."""

    file: str
    code: str | None
    guid: str | None
    text: str | None
    indicators: tuple[str, ...]


def load_translations(localization_dir: Path, work_dir: Path) -> dict[str, dict[str, str]]:
    """Load every language's texts from extracted ``.locres`` files.

    Args:
        localization_dir (Path): Directory holding ``<target>/<language>/*.locres``.
        work_dir (Path): Directory for the temporary JSON dumps.

    Returns:
        dict[str, dict[str, str]]: The text of each key, per language code.
    """
    translations: dict[str, dict[str, str]] = {}
    dump_path = work_dir / "locres_dump.json"

    for locres_path in sorted(localization_dir.glob("*/*/*.locres")):
        fs_assets.locres_dump(input=locres_path, output=dump_path)
        dump = json.loads(dump_path.read_text(encoding="utf-8"))
        language = translations.setdefault(locres_path.parent.name, {})
        for namespace in dump["namespaces"]:
            for entry in namespace["entries"]:
                language[entry["key"]] = entry["text"]

    return translations


def read_blueprints(blueprints_dir: Path) -> tuple[list[Blueprint], int]:
    """Read the blueprints among the extracted assets.

    Args:
        blueprints_dir (Path): Directory holding the extracted ``.uasset`` files.

    Returns:
        tuple[list[Blueprint], int]: The blueprints sorted by path, and how many
            assets were skipped because they aren't blueprints.
    """
    blueprints = []
    skipped = 0

    for path in sorted(blueprints_dir.rglob("*.uasset")):
        try:
            data = fs_assets.convert_to_json(path)
        except RuntimeError:
            skipped += 1
            continue

        content = json.dumps(data)
        display_name = data.get("DisplayName")
        if not isinstance(display_name, dict):
            display_name = {}
        blueprints.append(
            Blueprint(
                file=path.name,
                code=data.get("CodeName"),
                guid=display_name.get("Guid"),
                text=display_name.get("Text"),
                indicators=tuple(
                    name for name, pattern in STOCKPILE_INDICATORS.items() if pattern in content
                ),
            )
        )

    return blueprints, skipped


def group_by_stockpile_type(
    blueprints: Iterable[Blueprint],
) -> dict[StockpileType, list[Blueprint]]:
    """Match the blueprints to the stockpile types by CodeName.

    Args:
        blueprints (Iterable[Blueprint]): The blueprints to match.

    Returns:
        dict[StockpileType, list[Blueprint]]: The blueprints of every stockpile type.
    """
    grouped: dict[StockpileType, list[Blueprint]] = {
        member: [] for member in StockpileType if member != StockpileType.UNDEFINED
    }
    for blueprint in blueprints:
        for member, matches in grouped.items():
            if blueprint.code == member.value:
                matches.append(blueprint)
    return grouped


def _is_stockpile_structure(blueprint: Blueprint) -> bool:
    """Tell whether a blueprint looks like a player-accessible stockpile.

    Args:
        blueprint (Blueprint): The blueprint to check.

    Returns:
        bool: True for storage facilities and for bases with a stockpile.
    """
    if any(pattern in blueprint.file for pattern in EXCLUDE_PATTERNS):
        return False

    indicators = blueprint.indicators
    has_stockpile = "item_stockpile" in indicators or "generic_stockpile" in indicators
    is_base = has_stockpile and ("base_stockpile" in indicators or "static_base" in indicators)
    return "storage_facility" in indicators or is_base


def discover_new_structures(blueprints: list[Blueprint]) -> list[Blueprint]:
    """Find the stockpile-like structures that aren't a known stockpile type.

    Args:
        blueprints (list[Blueprint]): The blueprints to scan.

    Returns:
        list[Blueprint]: One blueprint for each new display name.
    """
    known_names = {
        match.text for matches in group_by_stockpile_type(blueprints).values() for match in matches
    }
    discovered: dict[str, Blueprint] = {}
    for blueprint in blueprints:
        if (
            blueprint.text
            and blueprint.text not in known_names
            and _is_stockpile_structure(blueprint)
        ):
            discovered.setdefault(blueprint.text, blueprint)
    return list(discovered.values())


def _print_translations(guid: str | None, translations: dict[str, dict[str, str]]) -> None:
    """Print the translation of a text in each language.

    Args:
        guid (str | None): The key of the text.
        translations (dict[str, dict[str, str]]): The texts per language code.
    """
    for language, texts in sorted(translations.items()):
        if guid in texts:
            print(f"  {language}: {texts[guid]}")


def print_stockpile_types(
    blueprints: list[Blueprint],
    translations: dict[str, dict[str, str]],
    show_guids: bool,
) -> None:
    """Print each stockpile type's name and translations.

    Args:
        blueprints (list[Blueprint]): The blueprints read from the game.
        translations (dict[str, dict[str, str]]): The texts per language code.
        show_guids (bool): Whether to show the text GUIDs.
    """
    for member, matches in group_by_stockpile_type(blueprints).items():
        print(f"\n{member.name} ({member.value}):")
        if not matches:
            print("  NOT FOUND: no blueprint has this CodeName")
        for match in matches:
            if match.guid is None:
                print(f"  {match.file} has no DisplayName of its own")
                continue
            if show_guids:
                print(f"  GUID: {match.guid}")
            _print_translations(guid=match.guid, translations=translations)


def print_new_structures(
    structures: list[Blueprint],
    translations: dict[str, dict[str, str]],
) -> None:
    """Print the structures that aren't a known stockpile type.

    Args:
        structures (list[Blueprint]): The structures found.
        translations (dict[str, dict[str, str]]): The texts per language code.
    """
    if not structures:
        print("\nNo new stockpile types detected.")
        return

    print("\n*** NEW STOCKPILE TYPES DETECTED ***")
    for structure in sorted(structures, key=lambda found: found.text or ""):
        print(f"\n{structure.text}")
        print(f"  File: {structure.file}")
        print(f"  CodeName: {structure.code}")
        print(f"  GUID: {structure.guid}")
        print(f"  Indicators: {list(structure.indicators)}")
        _print_translations(guid=structure.guid, translations=translations)


def _resolve_pak(pak: Path | None) -> Path:
    """Find the game PAK to read, exiting with an error if there is none.

    Args:
        pak (Path | None): The PAK given by the user, if any.

    Returns:
        Path: The game PAK.
    """
    if pak is None:
        directory = fs_assets.get_default_pak_directory()
        if directory is None:
            print("Error: game PAK not found in the Steam install; pass it with --pak")
            sys.exit(1)
        pak = directory / PAK_NAME

    if not pak.is_file():
        print(f"Error: PAK file not found: {pak}; pass the game PAK with --pak")
        sys.exit(1)

    return pak


def main() -> None:
    """Parse the command line and report what the game's PAK holds."""
    parser = argparse.ArgumentParser(
        description="List stockpile type names and translations from the game's PAK."
    )
    parser.add_argument("--pak", type=Path, help=f"Game PAK (default: {PAK_NAME} in Steam)")
    parser.add_argument("--show-guids", action="store_true", help="Show the text GUIDs")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Report structures that aren't a known stockpile type",
    )
    args = parser.parse_args()

    pak = _resolve_pak(args.pak)
    print(f"Using game files from: {pak}")

    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)
        fs_assets.unpak(pak, work_dir, include=LOCALIZATION_IN_PAK)
        fs_assets.unpak(pak, work_dir, include=BLUEPRINTS_IN_PAK)
        translations = load_translations(
            localization_dir=work_dir / LOCALIZATION_IN_PAK, work_dir=work_dir
        )
        blueprints, skipped = read_blueprints(work_dir / BLUEPRINTS_IN_PAK)

    print(f"Read {len(blueprints)} blueprints ({skipped} other assets skipped)")

    if args.discover:
        print_new_structures(
            structures=discover_new_structures(blueprints), translations=translations
        )
    else:
        print_stockpile_types(
            blueprints=blueprints, translations=translations, show_guids=args.show_guids
        )


if __name__ == "__main__":
    main()
