"""Stockpile model."""

from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem


class Stockpile(BaseModel):
    """Stockpile model."""

    name: str = Field(description="Name of the stockpile", default="")
    type: str = Field(description="Type of stockpile", default=StockpileType.UNDEFINED)
    faction: ItemFaction | None = Field(
        description="Controlling faction, if provided by the source", default=None
    )
    hex: str | None = Field(description="Hex region name", default=None)
    coords: StockpileCoords | None = Field(description="Map coordinates", default=None)
    is_reserve: bool = Field(description="Whether this is a reserve stockpile", default=False)
    items: list[StockpileItem] = Field(description="List of items", default_factory=list)
    timestamp: datetime = Field(description="last update datetime", default_factory=datetime.now)
    shard: str | None = Field(description="Shard name", default=None)
    ingame_timestamp: str | None = Field(description="In game timestamp", default=None)
    resolution: str | None = Field(description="Resolution of the screenshot", default=None)
    errors: list[str] | None = Field(
        description="List of errors encountered during processing", default=None
    )
    raw_timestamp: int | None = Field(
        description="Raw timestamp ticks from save file (for change tracking)",
        default=None,
        exclude=True,
    )

    def to_key(self) -> str:
        """Generate a unique key for this stockpile.

        The key is based on type, hex, coords, and name (for reserves).
        Used for tracking changes in the savefile monitor.

        Returns:
            str: Unique key for this stockpile.
        """
        coords_key = self.coords.to_key() if self.coords else "0,0"
        return f"{self.type}:{self.hex}:{coords_key}:{self.name}"

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize the timestamp as UTC without milliseconds or timezone."""
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "Logi",
                "type": StockpileType.SEAPORT,
                "hex": "Westgate",
                "coords": {"x": 0.457745, "y": 0.664469},
                "is_reserve": False,
                "items": [
                    cast(dict[str, Any], StockpileItem.model_config)
                    .get("json_schema_extra", {})
                    .get("example", {})
                ],
                "timestamp": "2024-01-04T09:00:00Z",
                "resolution": "1920x1080",
                "shard": "ABLE",
                "ingame_timestamp": "Day 1,293, 1906 Hours",
                "errors": ["No icon detected in group 1, index 67 with confidence 0.75"],
            }
        },
    )
