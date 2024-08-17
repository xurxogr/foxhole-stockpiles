from enum import Enum
from typing import Final

class stockpile_type(str, Enum):
    SEAPORT: Final = 'Seaport'
    STORAGE_DEPOT: Final = 'Storage Depot'
    TOWN_BASE: Final = 'Town Base'
    RELIC_BASE: Final = 'Relic Base'
    BUNKER_BASE: Final = 'Bunker Base'
    ENCAMPMENT: Final = 'Encampment'
    SAFE_HOUSE: Final = 'Safe House'
    UNDEFINED: Final = 'Undefined'
