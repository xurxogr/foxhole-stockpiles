from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from foxhole_stockpiles.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class Stockpile(BaseModel):
    name: str = Field(description="Name of the stockpile")
    type: stockpile_type = Field(description="Type of stockpile", default=stockpile_type.UNDEFINED)
    items: list[StockpileItem] | None = Field(description="List of items", default=[])
    timestamp: datetime | None = Field(description="last update datetime", default=None)
    resolution: str | None = Field(description="Resolution of the screenshot", default=None)

    @model_validator(mode="after")
    def validate(self):
        if not self.timestamp:
            self.timestamp = datetime.now()

        return self

    @field_serializer("type")
    def serialize_type(self, value):
        return value.value

    @field_serializer("timestamp")
    def serialize_timestamp(self, value):
        return value.isoformat()

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Logi",
                "type": stockpile_type.SEAPORT,
                "items": [StockpileItem.model_config["json_schema_extra"]["example"]],
                "timestamp": "2024-01-04T09:00:00Z",
                "resolution": "1920x1080"
            }
        }
    )
