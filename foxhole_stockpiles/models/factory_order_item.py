"""Factory order item model."""

from pydantic import BaseModel, ConfigDict, Field


class FactoryOrderItem(BaseModel):
    """An item of a factory order (the save keeps no quantities)."""

    slot: int = Field(
        description="Item position in the production queue (255 = unknown item)", ge=0, le=255
    )
    code: str | None = Field(description="Code of the item, if known", default=None)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "slot": 16,
                "code": "RifleC",
            }
        },
    )
