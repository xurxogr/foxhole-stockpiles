"""Stockpile model."""

from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class Stockpile(BaseModel):
    """Stockpile model."""

    name: str = Field(description="Name of the stockpile")
    type: StockpileType = Field(description="Type of stockpile", default=StockpileType.UNDEFINED)
    items: list[StockpileItem] = Field(description="List of items", default=[])
    timestamp: datetime = Field(description="last update datetime", default_factory=datetime.now)
    resolution: str | None = Field(description="Resolution of the screenshot", default=None)

    @field_serializer("type")
    def serialize_type(self, value: StockpileType) -> str:
        """Serialize the type."""
        return value.value

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize the timestamp."""
        return value.isoformat()

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Logi",
                "type": StockpileType.SEAPORT,
                "items": [
                    cast(dict[str, Any], StockpileItem.model_config)
                    .get("json_schema_extra", {})
                    .get("example", {})
                ],
                "timestamp": "2024-01-04T09:00:00Z",
                "resolution": "1920x1080",
            }
        },
    )
