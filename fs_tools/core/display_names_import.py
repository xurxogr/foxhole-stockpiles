"""Copy the names of the stockpile types from the game into the translations.

fs-assets extracts them from the game files, so a new game version only needs a new
extraction and another import, whose result is reviewed and committed.
"""

import json
from pathlib import Path
from typing import Any, Final

from pydantic import TypeAdapter

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from fs_tools.models.display_name_entry import DisplayNameEntry
from fs_tools.models.display_names_report import DisplayNamesReport

TRANSLATIONS_KEY: Final[str] = "stockpile_types"

_ENTRIES = TypeAdapter(list[DisplayNameEntry])


def read_stockpile_names(path: Path) -> dict[str, DisplayNameEntry]:
    """Read the stockpiles of an extraction of display names.

    Args:
        path (Path): The JSON written by fs-assets.

    Returns:
        dict[str, DisplayNameEntry]: Each stockpile by its code, sorted by code.

    Raises:
        ValueError: If the file is not a list of display names, or lacks a type that
            the application knows.
    """
    entries = _ENTRIES.validate_json(path.read_bytes())
    stockpiles = {entry.code: entry for entry in entries if entry.is_stockpile}
    known = {member.value for member in StockpileType} - {StockpileType.UNDEFINED.value}
    missing = sorted(known - set(stockpiles))
    if missing:
        raise ValueError(f"The extraction has no stockpile for: {', '.join(missing)}")
    return dict(sorted(stockpiles.items()))


def _with_names(translations: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    """Put the names of the stockpile types in a translation, replacing the old ones.

    Args:
        translations (dict[str, Any]): The content of a translation file.
        names (dict[str, str]): The name of each type in its language.

    Returns:
        dict[str, Any]: A new content with them.
    """
    return {**translations, TRANSLATIONS_KEY: names}


def import_stockpile_names(display_names: Path, translations_dir: Path) -> DisplayNamesReport:
    """Write the names of the stockpile types in every translation.

    A language the game has no name in gets the English one, so every translation
    has every type.

    Args:
        display_names (Path): The JSON written by fs-assets.
        translations_dir (Path): The directory of the translation files.

    Returns:
        DisplayNamesReport: What was written.
    """
    stockpiles = read_stockpile_names(display_names)
    languages: list[str] = []
    for path in sorted(translations_dir.glob("*.json")):
        language = path.stem
        names = {code: entry.name_in(language) for code, entry in stockpiles.items()}
        translations = json.loads(path.read_text(encoding="utf-8"))
        content = _with_names(translations=translations, names=names)
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        languages.append(language)
    known = {member.value for member in StockpileType}
    return DisplayNamesReport(
        languages=languages,
        imported=len(stockpiles),
        not_in_enum=[code for code in stockpiles if code not in known],
    )
