"""Refinery order model."""

from pydantic import BaseModel, ConfigDict, Field


class RefineryOrder(BaseModel):
    """A refinery order in the selected order queue."""

    slot: int = Field(
        description="Recipe position in the refinery list (255 = unknown recipe)", ge=0, le=255
    )
    code: str | None = Field(description="Code of the produced item, if known", default=None)
    source: int = Field(description="Material left to refine", ge=0, le=65000)
    refined: int = Field(description="Product ready to collect", ge=0, le=65000)
    duration: int = Field(description="Remaining seconds", ge=0, le=64800)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "slot": 0,
                "code": "Cloth",
                "source": 0,
                "refined": 50,
                "duration": 0,
            }
        },
    )
