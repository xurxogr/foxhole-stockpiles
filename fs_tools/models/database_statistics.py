"""Database statistics model."""

from pydantic import BaseModel, Field


class DatabaseStatistics(BaseModel):
    """Statistics about a template database."""

    resolutions: list[str] = Field(..., description="List of available resolutions")
    mod_stats: dict[str, dict[str, int]] = Field(
        ..., description="Template count per mod per resolution (mod -> {resolution -> count})"
    )
