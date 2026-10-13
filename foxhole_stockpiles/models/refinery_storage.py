"""Refinery storage model."""

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.models.refinery_access import RefineryAccess


class RefineryStorage(BaseModel):
    """Finished refinery product stored for an owner and recipe."""

    access: RefineryAccess = Field(description="Owner of the stored product")
    slot: int = Field(
        description="Recipe position in the refinery list (255 = unknown recipe)", ge=0, le=255
    )
    code: str | None = Field(description="Code of the stored item, if known", default=None)
    refined: int = Field(description="Stored product quantity", ge=0, le=65000)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "access": cast(dict[str, Any], RefineryAccess.model_config)
                .get("json_schema_extra", {})
                .get("example", {}),
                "slot": 1,
                "code": "Diesel",
                "refined": 5309,
            }
        },
    )
