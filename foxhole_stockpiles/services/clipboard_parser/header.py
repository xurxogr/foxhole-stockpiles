"""Parsing of the clipboard export's header line."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.services.clipboard_parser.type_aliases import _type_from_display

logger = logging.getLogger(__name__)

# In-game export timestamp, e.g. "2026.06.23-16.30.38".
_TIMESTAMP_FORMAT = "%Y.%m.%d-%H.%M.%S"

# Header line: "<hex> - <town> - <type> - <name> - X: <x> Y: <y>,<timestamp>".
# The coords/timestamp tail is unambiguous (and not localized), so anchor on it
# and treat the rest as the " - "-joined prefix.
_HEADER_RE = re.compile(
    r"^(?P<prefix>.+) - X:\s*(?P<x>[-+]?\d*\.?\d+)\s+Y:\s*(?P<y>[-+]?\d*\.?\d+),(?P<ts>.+)$"
)


@dataclass(frozen=True)
class _Header:
    """Parsed header line fields (town/city intentionally dropped)."""

    hex: str
    type: str
    name: str
    coords: StockpileCoords
    timestamp: datetime | None


def _parse_header(line: str) -> _Header | None:
    """Parse the header line; the gate for "is this a stockpile export".

    Args:
        line (str): The candidate header line.

    Returns:
        _Header | None: Parsed header, or None if the line is not a header.
    """
    match = _HEADER_RE.match(line.strip())
    if not match:
        return None

    parts = [p.strip() for p in match.group("prefix").split(" - ")]
    if len(parts) < 3:
        return None

    # parts: [hex, town, type, name...]. The town/city is dropped. The name may
    # itself contain " - ", so any extra segments are folded back into it.
    hex_name = parts[0]
    type_display = parts[2]
    name = " - ".join(parts[3:]) if len(parts) > 3 else ""

    try:
        coords = StockpileCoords(x=float(match.group("x")), y=float(match.group("y")))
    except ValueError:
        return None

    timestamp: datetime | None = None
    try:
        timestamp = datetime.strptime(match.group("ts").strip(), _TIMESTAMP_FORMAT)
    except ValueError:
        logger.debug("Could not parse clipboard timestamp: %r", match.group("ts"))

    return _Header(
        hex=hex_name,
        type=_type_from_display(type_display),
        name=name,
        coords=coords,
        timestamp=timestamp,
    )
