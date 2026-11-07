"""Stockpiles drawn as one image."""

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.models.stockpile import Stockpile


class StockpileGroup(BaseModel):
    """What one image shows, and the stockpiles it comes from."""

    drawn: Stockpile = Field(description="The stockpile drawn: one of them, or their merge")
    sources: list[Stockpile] = Field(description="The stockpiles of the send it stands for")

    model_config = ConfigDict(extra="forbid", frozen=True)
