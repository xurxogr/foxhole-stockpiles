"""Which public stockpiles an output receives."""

from enum import StrEnum


class PublicStockpileFilter(StrEnum):
    """Which public stockpiles of a send reach an output.

    Reserve stockpiles always do.
    """

    ALL = "all"
    NONE = "none"
    # Only those of structures that cannot hold reserves, such as a bunker: in a
    # seaport, the reserves are what matters.
    NON_RESERVABLE = "non_reservable"
