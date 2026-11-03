"""Tests for the clipboard header line: what it accepts and what it costs to reject."""

import time
from typing import Final

import pytest

from foxhole_stockpiles.services.clipboard_parser.header import _HEADER_RE, _parse_header

_TAIL: Final[str] = ",2026.06.23-16.30.38"
_LINEAR_TIME_BOUND_SECONDS: Final[float] = 1.0


def _header(x: str, y: str = "0.5", name: str = "Public") -> str:
    """Build a header line.

    Args:
        x (str): The X coordinate text.
        y (str): The Y coordinate text.
        name (str): The stockpile name.

    Returns:
        str: The header line.
    """
    return f"Hex - Town - Seaport - {name} - X: {x} Y: {y}{_TAIL}"


@pytest.mark.parametrize(
    ("text", "value"),
    [("0.5", 0.5), (".5", 0.5), ("1", 1.0), ("+0.25", 0.25), ("0.4577449", 0.4577449)],
)
def test_coordinate_forms_keep_being_accepted(text: str, value: float) -> None:
    """Every number form the header understood before stays readable."""
    header = _parse_header(_header(x=text))

    assert header is not None
    assert header.coords is not None
    assert header.coords.x == value


@pytest.mark.parametrize("text", ["1.", ".", "", "1.2.3", "abc"])
def test_malformed_coordinates_are_not_a_header(text: str) -> None:
    """A malformed number means the line is not an export header."""
    assert _parse_header(_header(x=text)) is None


@pytest.mark.parametrize(
    "line",
    [
        f"a - b - c - X: {'1' * 64_000}",
        f"a - b - c - X: 1 Y: {'1' * 64_000}",
        f"a - b - c - X: {'1' * 64_000}{_TAIL}",
        " - X: 1" * 10_000,
    ],
    ids=["digits-in-x", "digits-in-y", "digits-before-tail", "repeated-marker"],
)
def test_rejecting_a_long_line_takes_linear_time(line: str) -> None:
    """The pattern must not backtrack quadratically: the GIL would freeze the GUI."""
    started = time.perf_counter()

    assert _HEADER_RE.match(line) is None

    assert time.perf_counter() - started < _LINEAR_TIME_BOUND_SECONDS


def test_an_oversized_header_is_rejected() -> None:
    """No real export has a header this long, so it is not parsed at all."""
    assert _parse_header(_header(x="0.5", name="n" * 2_000)) is None


def test_a_long_stockpile_name_is_still_a_header() -> None:
    """The limit leaves room for any name the game allows."""
    header = _parse_header(_header(x="0.5", name="n" * 200))

    assert header is not None
    assert header.name == "n" * 200
