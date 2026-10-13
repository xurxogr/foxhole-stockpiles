"""Refinery model."""

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.refinery_access_level import RefineryAccessLevel
from foxhole_stockpiles.models.refinery_access import RefineryAccess
from foxhole_stockpiles.models.refinery_order import RefineryOrder
from foxhole_stockpiles.models.refinery_storage import RefineryStorage


class Refinery(BaseModel):
    """Refinery orders and stored products of a refinery stockpile."""

    orders_access: RefineryAccess | None = Field(
        description="Order queue selected by the player who opened the tooltip", default=None
    )
    orders: list[RefineryOrder] = Field(
        description="Orders of the selected queue", default_factory=list
    )
    storages: list[RefineryStorage] = Field(
        description="Finished product stored per owner and recipe", default_factory=list
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "orders_access": {"level": RefineryAccessLevel.PUBLIC},
                "orders": [
                    cast(dict[str, Any], RefineryOrder.model_config)
                    .get("json_schema_extra", {})
                    .get("example", {})
                ],
                "storages": [
                    cast(dict[str, Any], RefineryStorage.model_config)
                    .get("json_schema_extra", {})
                    .get("example", {})
                ],
            }
        },
    )
