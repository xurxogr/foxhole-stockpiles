"""Tests for handlers.formula_guard module."""

import pytest

from foxhole_stockpiles.handlers.formula_guard import neutralize_formula


@pytest.mark.parametrize(
    "value",
    ["=1+1", "+1", "-1", "@SUM(A1)", "\t=1", "\r=1", " =1", "  +1"],
)
def test_formula_like_values_get_a_text_prefix(value: str) -> None:
    """A value a spreadsheet would evaluate is forced to plain text."""
    assert neutralize_formula(value) == "'" + value


@pytest.mark.parametrize("value", ["Seaport", "a=b", "", "1+1", "   "])
def test_plain_values_are_unchanged(value: str) -> None:
    """A value a spreadsheet would not evaluate is returned untouched."""
    assert neutralize_formula(value) == value
