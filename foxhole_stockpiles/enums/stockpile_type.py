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

    def has_custom_name(self) -> bool:
        """Check if this stockpile type supports custom player-given names.

        Only player-built structures (Storage Depot, Seaport, Aircraft Depot)
        can have custom names. Base types use their type as the display name.

        Returns:
            bool: True if this stockpile type can have a custom name.
        """
        return self in (
            StockpileType.STORAGE_DEPOT,
            StockpileType.SEAPORT,
            StockpileType.AIRCRAFT_DEPOT,
        )
