from datetime import datetime
from uuid import uuid4

from numpy import ndarray
from pydantic import BaseModel, ConfigDict, Field
from uuid_shortener import ShortUuidGenerator

from foxhole_stockpiles.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class Stockpile(BaseModel):
    uid: str | None = Field(description="Internal id", default_factory=ShortUuidGenerator(uuid_fn=uuid4))
    name: str = Field(description="Name of the stockpile")
    type: stockpile_type = Field(description="Type of stockpile", default=stockpile_type.UNDEFINED)
    image: ndarray | None = Field(description="Image data", default=None, exclude=True)
    items: list[StockpileItem] | None = Field(description="List of items", default=[])
    timestamp: datetime | None = Field(description="last update datetime", default=None)
    region: str = Field(description="Name of the region the stockpile belongs to", default=None)
    code: str = Field(description="Stockpile access code", default=None)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Logi",
                "type": stockpile_type.SEAPORT,
                "items": [StockpileItem.model_config["json_schema_extra"]["example"]],
                "timestamp": "2024-01-04T09:00:00Z"
            }
        }
    )
