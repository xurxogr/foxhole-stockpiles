"""Tests for enums.refinery_access_level module."""

import pytest

from foxhole_stockpiles.enums.refinery_access_level import RefineryAccessLevel


class TestRefineryAccessLevelEnum:
    """Test suite for RefineryAccessLevel enum values."""

    def test_enum_values(self) -> None:
        """Test that all RefineryAccessLevel values are correctly defined."""
        assert RefineryAccessLevel.PERSONAL.value == "personal"
        assert RefineryAccessLevel.PUBLIC.value == "public"
        assert RefineryAccessLevel.SQUAD.value == "squad"


class TestFromString:
    """Test suite for RefineryAccessLevel.from_string."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("personal", RefineryAccessLevel.PERSONAL),
            ("PUBLIC", RefineryAccessLevel.PUBLIC),
            ("  squad  ", RefineryAccessLevel.SQUAD),
            ("ERefineryOrderAccessLevel::Squad", RefineryAccessLevel.SQUAD),
            ("erefineryorderaccesslevel::PERSONAL", RefineryAccessLevel.PERSONAL),
        ],
    )
    def test_valid_values(self, value: str, expected: RefineryAccessLevel) -> None:
        """Test that plain and in-game names resolve case-insensitively."""
        assert RefineryAccessLevel.from_string(value) is expected

    @pytest.mark.parametrize("value", ["", "team", "ERefineryOrderAccessLevel::Team"])
    def test_invalid_values_raise(self, value: str) -> None:
        """Test that unknown values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid refinery access level"):
            RefineryAccessLevel.from_string(value)
