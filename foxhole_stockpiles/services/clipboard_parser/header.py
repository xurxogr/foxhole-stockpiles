"""Parsing of the clipboard export's header line."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from foxhole_stockpiles.models.clipboard_header import ClipboardHeader
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.services.clipboard_parser.type_aliases import _type_from_display

logger = logging.getLogger(__name__)

# In-game export timestamp, e.g. "2026.06.23-16.30.38".
_TIMESTAMP_FORMAT = "%Y.%m.%d-%H.%M.%S"

# Header line: "<hex> - <town> - <type> - <name> - X: <x> Y: <y>,<timestamp>".
# The coords/timestamp tail is unambiguous (and not localized), so anchor on it
# and treat the rest as the " - "-joined prefix.
# The number has one way to match each text: this runs on whatever the clipboard
# holds, and backtracking over a long run of digits would stall the whole process.
_NUMBER = r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)"
_HEADER_RE = re.compile(
    rf"^(?P<prefix>.+) - X:\s*(?P<x>{_NUMBER})\s+Y:\s*(?P<y>{_NUMBER}),(?P<ts>.+)$"
)

# Far above any real export header, whose free text is one short stockpile name.
_MAX_HEADER_CHARS = 1024


def _parse_header(line: str) -> ClipboardHeader | None:
    """Parse the header line; the gate for "is this a stockpile export".

    Args:
        line (str): The candidate header line.

    Returns:
        ClipboardHeader | None: Parsed header, or None if the line is not a header.
    """
    if len(line) > _MAX_HEADER_CHARS:
        return None

    match = _HEADER_RE.match(line.strip())
    if not match:
        return None

    parts = [p.strip() for p in match.group("prefix").split(" - ")]
    if len(parts) < 3:
        return None

    # parts: [hex, town, type, name...]. The name may itself contain " - ", so any
    # extra segments are folded back into it.
    hex_name = parts[0]
    town = parts[1]
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

    return ClipboardHeader(
        hex=hex_name,
        town=town,
        type=_type_from_display(type_display),
        name=name,
        coords=coords,
        timestamp=timestamp,
    )
