"""Factory order model."""

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.models.factory_order_item import FactoryOrderItem


class FactoryOrder(BaseModel):
    """A factory order of the player who opened the tooltip."""

    queue: int = Field(description="Production queue position in the factory", ge=0, le=255)
    # Free-form like Stockpile.type, so a new in-game queue does not break validation.
    queue_type: str | None = Field(
        description="Production queue name (e.g. SmallArms, Vehicles), if known", default=None
    )
    duration: int = Field(
        description="Seconds until the order is done, counting the orders ahead (0 = ready)",
        ge=0,
        le=64800,
    )
    items: list[FactoryOrderItem] = Field(description="Ordered items", default_factory=list)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "queue": 0,
                "queue_type": "SmallArms",
                "duration": 0,
                "items": [
                    cast(dict[str, Any], FactoryOrderItem.model_config)
                    .get("json_schema_extra", {})
                    .get("example", {})
                ],
            }
        },
    )
