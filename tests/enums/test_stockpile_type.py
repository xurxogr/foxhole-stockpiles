"""Tests for the stockpile type enum."""

import pytest

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.services.clipboard_parser.type_aliases import _type_from_display
from foxhole_stockpiles.services.scanner import _EXTERNAL_TYPE_BY_NAME

ENCAMPMENT_CODE = "ForwardBase1"
SAFE_HOUSE_CODE = "GarrisonStation"


def test_encampment_and_safe_house_use_their_in_game_code_names() -> None:
    """Each member holds the CodeName of the structure the game shows with that name."""
    assert StockpileType.ENCAMPMENT.value == ENCAMPMENT_CODE
    assert StockpileType.SAFE_HOUSE.value == SAFE_HOUSE_CODE


@pytest.mark.parametrize(
    ("ocr_name", "code"),
    [("Encampment", ENCAMPMENT_CODE), ("SafeHouse", SAFE_HOUSE_CODE)],
)
def test_ocr_types_map_to_the_in_game_code_name(ocr_name: str, code: str) -> None:
    """A type recognized from a screenshot gets the same CodeName as in a save file."""
    assert _EXTERNAL_TYPE_BY_NAME[ocr_name].value == code


@pytest.mark.parametrize(
    ("display", "code"),
    [
        ("Encampment", ENCAMPMENT_CODE),
        ("Feldlager", ENCAMPMENT_CODE),
        ("Safe House", SAFE_HOUSE_CODE),
        ("Unterschlupf", SAFE_HOUSE_CODE),
    ],
)
def test_clipboard_types_map_to_the_in_game_code_name(display: str, code: str) -> None:
    """A type read from the clipboard gets the same CodeName as in a save file."""
    assert _type_from_display(display) == code
