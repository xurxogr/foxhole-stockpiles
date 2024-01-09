from datetime import datetime
from typing import Final

from pydantic import BaseModel
from pydantic import conlist
from pydantic import Field

from foxhole_stockpiles.models.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.models.image import Image

class Stockpile(BaseModel):
    UNNAMED: Final = 'Unnamed'

    name: str = Field(description="Name of the field", default="Unnamed")
    type: stockpile_type = Field(description="Type of stockpile", default=stockpile_type.UNDEFINED)
    image: Image = Field(description="Image data (name and image)", default=None)
    items: conlist(item_type=StockpileItem) | None = Field(description="List of rectangles containing the items", default=[])
    timestamp: datetime | None = Field(description="last update datetime", default=None)

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "name": "Logi",
                "type": stockpile_type.SEAPORT,
                "image": Image.Config.json_schema_extra,
                "items": [StockpileItem.Config.json_schema_extra],
                "timestamp": "2024-01-04T09:00:00Z"
            }
        }
