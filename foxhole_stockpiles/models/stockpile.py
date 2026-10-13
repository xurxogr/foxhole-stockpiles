"""Stockpile model."""

from datetime import datetime
from typing import Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.factory_order import FactoryOrder
from foxhole_stockpiles.models.refinery import Refinery
from foxhole_stockpiles.models.stockpile_coords import StockpileCoords
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.models.stockpile_tech import StockpileTech


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
    tech: StockpileTech | None = Field(
        description="Garrison/upgrade tech build progress (main stockpile of a base only)",
        default=None,
    )
    refinery: Refinery | None = Field(
        description="Refinery orders and storages (main Refinery stockpile only), if provided",
        default=None,
    )
    factory_orders: list[FactoryOrder] | None = Field(
        description="Factory orders of the player who opened the tooltip (main stockpile only)",
        default=None,
    )
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

    @model_validator(mode="after")
    def check_type_specific_data(self) -> Self:
        """Reject type-specific data on the wrong type or on a reserve stockpile.

        Tech, refinery and factory orders only belong to the main stockpile of
        the structure types that have them. All of them are optional.

        Returns:
            Self: The validated model.

        Raises:
            ValueError: If a type-specific field is set on another type or on a reserve.
        """
        rules = (
            ("tech", self.tech, StockpileType.has_tech(self.type)),
            ("refinery", self.refinery, self.type == StockpileType.REFINERY),
            ("factory_orders", self.factory_orders, StockpileType.has_factory_orders(self.type)),
        )
        for name, value, allowed in rules:
            if value is None:
                continue
            if not allowed:
                raise ValueError(f"{name} is not allowed on '{self.type}' stockpiles")
            if self.is_reserve:
                raise ValueError(f"{name} is not allowed on reserve stockpiles")
        return self

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
