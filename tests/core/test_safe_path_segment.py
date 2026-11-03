"""Text from a stockpile ends up in file names, and others can control it."""

import pytest

from foxhole_stockpiles.core.safe_path_segment import safe_path_segment


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Logi", "Logi"),
        ("Склад 1", "Склад 1"),
        ("../../etc/foo", "_.._etc_foo"),
        ("a:b", "a_b"),
        ("..", "_"),
        ("", "_"),
        ("   ", "_"),
        ("nul", "_nul"),
        ("COM1.txt", "_COM1.txt"),
    ],
)
def test_value_becomes_one_safe_path_segment(value: str, expected: str) -> None:
    """Separators, relative segments and reserved names do not survive."""
    assert safe_path_segment(value) == expected
