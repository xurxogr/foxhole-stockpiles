from datetime import datetime
from typing import Final

from numpy import ndarray
from pydantic import BaseModel
from pydantic import conlist
from pydantic import Field

from foxhole_stockpiles.models.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class Stockpile(BaseModel):
    UNNAMED: Final = 'Unnamed'

    name: str = Field(description="Name of the stockpile", default="Unnamed")
    type: stockpile_type = Field(description="Type of stockpile", default=stockpile_type.UNDEFINED)
    image: ndarray | None = Field(description="Image data", default=None, exclude=True)
    items: conlist(item_type=StockpileItem) | None = Field(description="List of items", default=[])
    timestamp: datetime | None = Field(description="last update datetime", default=None)

    class Config:
        arbitrary_types_allowed=True
        use_enum_values = True
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "name": "Logi",
                "type": stockpile_type.SEAPORT,
                "image": [],
                "items": [StockpileItem.Config.json_schema_extra],
                "timestamp": "2024-01-04T09:00:00Z"
            }
        }
