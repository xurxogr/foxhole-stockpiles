"""Stockpile tech model."""

from typing import Annotated

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal

TECH_PROGRESS_MAX = 100


TechProgress = Annotated[int | None, Field(ge=0, le=TECH_PROGRESS_MAX)]
"""Build progress of a tech slot (0-100)."""


class StockpileTech(BaseModel):
    """Garrison/upgrade tech build progress (0-100 per slot) of a base.

    Only the slots that exist for the base type are set. Input accepts the
    PascalCase keys emitted by fs-sav (e.g. ``ProvisionalGarrison``).
    """

    provisional_garrison: TechProgress = Field(
        description="Provisional garrison progress", default=None
    )
    small_garrison: TechProgress = Field(description="Small garrison progress", default=None)
    large_garrison: TechProgress = Field(description="Large garrison progress", default=None)
    t1_garrison: TechProgress = Field(description="Tier 1 garrison progress", default=None)
    t2_garrison: TechProgress = Field(description="Tier 2 garrison progress", default=None)
    t3_garrison: TechProgress = Field(description="Tier 3 garrison progress", default=None)
    artillery_garrison: TechProgress = Field(
        description="Artillery garrison progress", default=None
    )
    t1_support_bunkers: TechProgress = Field(
        description="Tier 1 support bunkers progress", default=None
    )
    t3_support_bunkers: TechProgress = Field(
        description="Tier 3 support bunkers progress", default=None
    )
    deployment: TechProgress = Field(description="Deployment progress", default=None)
    advanced_bunkers: TechProgress = Field(description="Advanced bunkers progress", default=None)
    radio_station: TechProgress = Field(description="Radio station progress", default=None)
    artillery_shelter: TechProgress = Field(description="Artillery shelter progress", default=None)
    industry: TechProgress = Field(description="Industry progress", default=None)
    occupied_town: TechProgress = Field(description="Occupied town progress", default=None)
    fortifications: TechProgress = Field(description="Fortifications progress", default=None)

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=AliasGenerator(validation_alias=to_pascal),
        validate_by_name=True,
        validate_by_alias=True,
        json_schema_extra={
            "example": {
                "provisional_garrison": 100,
                "small_garrison": 100,
                "large_garrison": 70,
                "t1_garrison": 100,
                "t2_garrison": 0,
            }
        },
    )
