"""Stockpile type enum."""

from enum import StrEnum


class StockpileType(StrEnum):
    """Stockpile type enum."""

    # Bases (order from the game).
    # Bunker and town bases can have different level but the name is the same
    ENCAMPMENT = "Encampment"
    KEEP = "Keep"
    SAFE_HOUSE = "Safe House"
    RELIC_BASE = "Relic Base"
    BUNKER_BASE = "Bunker Base"
    BORDER_BASE = "Border Base"
    TOWN_BASE = "Town Base"
    BMS_LONGHOOK = "BMS - Longhook"

    # Structures (order from the game)
    STORAGE_DEPOT = "Storage Depot"
    SEAPORT = "Seaport"

    UNDEFINED = "Undefined"
