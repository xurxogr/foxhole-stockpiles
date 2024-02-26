from datetime import datetime
from uuid_shortener import ShortUuidGenerator
from uuid import uuid4

from numpy import ndarray
from pydantic import BaseModel
from pydantic import conlist
from pydantic import Field

from foxhole_stockpiles.models.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class Stockpile(BaseModel):
    uid: str | None = Field(description="Internal id", default_factory=ShortUuidGenerator(uuid_fn=uuid4))
    name: str = Field(description="Name of the stockpile")
    type: stockpile_type = Field(description="Type of stockpile", default=stockpile_type.UNDEFINED)
    image: ndarray | None = Field(description="Image data", default=None, exclude=True)
    items: conlist(item_type=StockpileItem) | None = Field(description="List of items", default=[])
    timestamp: datetime | None = Field(description="last update datetime", default=None)
    region: str = Field(description="Name of the region the stockpile belongs to", default=None)
    code: str = Field(description="Stockpile access code", default=None)

    class Config:
        arbitrary_types_allowed=True
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
