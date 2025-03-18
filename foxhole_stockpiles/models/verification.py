"""Verification model module."""

from pydantic import BaseModel, Field


class Verification(BaseModel):
    """Verification Model."""

    name: str | None = Field(description="Name of the player", default=None)
    level: int | None = Field(description="Level of the player", default=None)
    colonial: bool | None = Field(description="Whether the player is colonial", default=None)
    regiment: bool | None = Field(description="Whether the player has a regiment", default=None)
    shard: str | None = Field(description="Shard of the player", default=None)
