"""Stockpile type enum."""

from __future__ import annotations

from enum import StrEnum


class StockpileType(StrEnum):
    """Stockpile type enum.

    Values are the in-game CodeNames used in save files.
    """

    # Bases (in-game CodeNames)
    ENCAMPMENT = "GarrisonStation"
    KEEP = "Keep"
    SAFE_HOUSE = "ForwardBase1"
    RELIC_BASE = "RelicBase1"
    BUNKER_BASE_1 = "FortBaseT1"
    BUNKER_BASE_2 = "FortBaseT2"
    BUNKER_BASE_3 = "FortBaseT3"
    BORDER_BASE = "BorderBase"
    TOWN_BASE_1 = "TownBase1"
    TOWN_BASE_2 = "TownBase2"
    TOWN_BASE_3 = "TownBase3"
    UNDERGROUND_FORTRESS = "FortGarrisonStation"
    BMS_LONGHOOK = "LargeShipBaseShip"
    BMS_BLUEFIN = "LargeShipStorageShip"

    # Structures (in-game CodeNames)
    STORAGE_DEPOT = "StorageFacility"
    SEAPORT = "Seaport"
    AIRCRAFT_DEPOT = "AircraftDepot"

    # Factories (in-game CodeNames)
    FACTORY = "Factory"
    MASS_PRODUCTION_FACTORY = "MassProduction"

    # Facilities (in-game CodeNames)
    HOSPITAL = "Hospital"
    REFINERY = "Refinery"
    MAINTENANCE_TUNNEL = "MaintenanceTunnel"
    SMALL_ARMS_FACTORY = "FacilityFactorySmallArms"
    MODIFICATION_CENTER = "FacilityModificationCenter"
    TRANSFER_LIQUID = "FacilityTransferLiquid"
    TRANSFER_MATERIAL = "FacilityTransferMaterial"
    TRANSFER_RESOURCE = "FacilityTransferResource"
    VEHICLE_FACTORY_1 = "FacilityVehicleFactory1"
    VEHICLE_FACTORY_2 = "FacilityVehicleFactory2"
    VEHICLE_FACTORY_3 = "FacilityVehicleFactory3"

    UNDEFINED = "Undefined"

    @staticmethod
    def has_tech(value: str) -> bool:
        """Tell whether a stockpile type has a garrison/upgrade tech tree.

        Args:
            value (str): Stockpile type CodeName (may be unknown).

        Returns:
            bool: True for the base types with a tech tree.
        """
        return value in _TECH_TYPES

    @staticmethod
    def has_factory_orders(value: str) -> bool:
        """Tell whether a stockpile type takes factory orders.

        Args:
            value (str): Stockpile type CodeName (may be unknown).

        Returns:
            bool: True for Factory and Mass Production Factory.
        """
        return value in _FACTORY_ORDER_TYPES


_TECH_TYPES: frozenset[str] = frozenset(
    {
        StockpileType.SAFE_HOUSE,
        StockpileType.KEEP,
        StockpileType.BORDER_BASE,
        StockpileType.RELIC_BASE,
        StockpileType.ENCAMPMENT,
        StockpileType.TOWN_BASE_1,
        StockpileType.TOWN_BASE_2,
        StockpileType.TOWN_BASE_3,
        StockpileType.BUNKER_BASE_1,
        StockpileType.BUNKER_BASE_2,
        StockpileType.BUNKER_BASE_3,
    }
)

_FACTORY_ORDER_TYPES: frozenset[str] = frozenset(
    {StockpileType.FACTORY, StockpileType.MASS_PRODUCTION_FACTORY}
)
