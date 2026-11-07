"""Copying the names of the stockpile types from the game into the translations."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from fs_tools.core.display_names_import import import_stockpile_names, read_stockpile_names


def _entry(code: str, name: str, stockpile: bool = True, **names: str) -> dict[str, Any]:
    return {
        "CodeName": code,
        "DisplayName": name,
        "DisplayNameLocales": {"en": name, **names},
        "Pinnable": True,
        "Stockpile": stockpile,
    }


def _all_types() -> list[dict[str, Any]]:
    return [
        _entry(member.value, f"Name of {member.value}")
        for member in StockpileType
        if member is not StockpileType.UNDEFINED
    ]


def _write(path: Path, entries: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


@pytest.fixture
def translations(tmp_path: Path) -> Path:
    """Create two translation files.

    Args:
        tmp_path (Path): The temporary directory.

    Returns:
        Path: Their directory.
    """
    directory = tmp_path / "translations"
    directory.mkdir()
    for language in ("de", "es"):
        content = {"language_code": language, "common": {"ok": "OK"}}
        (directory / f"{language}.json").write_text(json.dumps(content), encoding="utf-8")
    return directory


def _read(directory: Path, language: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(
        (directory / f"{language}.json").read_text(encoding="utf-8")
    )
    return result


def test_each_language_gets_the_names_of_the_game(tmp_path: Path, translations: Path) -> None:
    """In its language, and in English where the game has none."""
    entries = [*_all_types()[1:], _entry(StockpileType.ENCAMPMENT.value, "Encampment", de="Feld")]
    source = _write(tmp_path / "names.json", entries)

    report = import_stockpile_names(display_names=source, translations_dir=translations)

    assert report.languages == ["de", "es"]
    assert _read(translations, "de")["stockpile_types"]["ForwardBase1"] == "Feld"
    assert _read(translations, "es")["stockpile_types"]["ForwardBase1"] == "Encampment"


def test_the_rest_of_the_translation_stays(tmp_path: Path, translations: Path) -> None:
    """Only the names of the types are replaced."""
    source = _write(tmp_path / "names.json", _all_types())

    import_stockpile_names(display_names=source, translations_dir=translations)

    content = _read(translations, "de")
    assert content["common"] == {"ok": "OK"}
    assert list(content)[:2] == ["language_code", "common"]


def test_names_of_a_previous_import_are_replaced(tmp_path: Path, translations: Path) -> None:
    """A type the game renamed or removed does not keep its old name."""
    source = _write(tmp_path / "names.json", _all_types())
    path = translations / "de.json"
    path.write_text(json.dumps({"stockpile_types": {"Gone": "Old"}}), encoding="utf-8")

    import_stockpile_names(display_names=source, translations_dir=translations)

    assert "Gone" not in _read(translations, "de")["stockpile_types"]


def test_structures_that_are_not_stockpiles_are_left_out(tmp_path: Path) -> None:
    """A pinnable without items has no type to name."""
    source = _write(tmp_path / "names.json", [*_all_types(), _entry("Shipyard", "Shipyard", False)])

    assert "Shipyard" not in read_stockpile_names(source)


def test_stockpiles_the_enum_lacks_are_imported_and_reported(
    tmp_path: Path, translations: Path
) -> None:
    """A save file can have them, and the enum may need them."""
    source = _write(tmp_path / "names.json", [*_all_types(), _entry("NewMine", "New Mine")])

    report = import_stockpile_names(display_names=source, translations_dir=translations)

    assert report.not_in_enum == ["NewMine"]
    assert _read(translations, "de")["stockpile_types"]["NewMine"] == "New Mine"


def test_a_type_of_the_enum_missing_from_the_extraction_fails(
    tmp_path: Path, translations: Path
) -> None:
    """Nothing is written, so the translations do not lose its name."""
    source = _write(tmp_path / "names.json", _all_types()[1:])
    before = (translations / "de.json").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match=StockpileType.ENCAMPMENT.value):
        import_stockpile_names(display_names=source, translations_dir=translations)

    assert (translations / "de.json").read_text(encoding="utf-8") == before


def test_a_file_that_is_not_an_extraction_fails(tmp_path: Path) -> None:
    """Its problem is reported instead of writing wrong names."""
    source = _write(tmp_path / "names.json", [{"CodeName": "X"}])

    with pytest.raises(ValidationError):
        read_stockpile_names(source)
