"""Tests for mod name validation."""

import pytest

from fs_tools.core.mod_name import validate_mod_name


def test_valid_name_is_stripped() -> None:
    """Surrounding whitespace is removed; letters, digits, spaces, _ and - are kept."""
    assert validate_mod_name("  Clean Icons_v2-final  ") == "Clean Icons_v2-final"


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name_is_rejected(name: str) -> None:
    """An empty or blank name is rejected."""
    with pytest.raises(ValueError, match="empty"):
        validate_mod_name(name)


def test_too_long_name_is_rejected() -> None:
    """Names over 100 characters are rejected."""
    with pytest.raises(ValueError, match="too long"):
        validate_mod_name("a" * 101)


@pytest.mark.parametrize("name", ["../vanilla", "mods/clean", "clean\\icons", "clean;rm"])
def test_unsafe_characters_are_rejected(name: str) -> None:
    """Path separators and other punctuation are rejected."""
    with pytest.raises(ValueError, match="only contain"):
        validate_mod_name(name)
