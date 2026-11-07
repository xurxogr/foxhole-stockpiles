"""How the stockpiles of a send share an image."""

from enum import StrEnum


class StockpileGrouping(StrEnum):
    """Which stockpiles of a send are drawn as one.

    A group of a single stockpile is drawn as it is.
    """

    NONE = "none"
    ALL = "all"
    HEX = "hex"
    LOCATION = "location"
