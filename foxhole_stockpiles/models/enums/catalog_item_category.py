from enum import Enum
from typing import Final

class catalog_item_category(str, Enum):
    HEAVY_AMMO: Final = 'HeavyAmmo'
    HEAVY_ARMS: Final = 'HeavyArms'
    MEDICAL: Final = 'Medical'
    SMALL_ARMS: Final = 'SmallArms'
    SUPPLIES: Final = 'Supplies'
    UNIFORMS: Final = 'Uniforms'
    UTILITY: Final = 'Utility'
