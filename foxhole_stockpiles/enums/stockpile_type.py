from enum import StrEnum


class stockpile_type(StrEnum):
    SEAPORT = 'Seaport'
    STORAGE_DEPOT = 'Storage Depot'
    TOWN_BASE = 'Town Base'
    RELIC_BASE = 'Relic Base'
    BUNKER_BASE = 'Bunker Base'
    ENCAMPMENT = 'Encampment'
    SAFE_HOUSE = 'Safe House'
    UNDEFINED = 'Undefined'
