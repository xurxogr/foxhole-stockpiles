"""Clipboard export header model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from foxhole_stockpiles.models.stockpile_coords import StockpileCoords


class ClipboardHeader(BaseModel):
    """Parsed header line fields of a clipboard export."""

    hex: str
    town: str
    type: str
    name: str
    coords: StockpileCoords
    timestamp: datetime | None

    model_config = ConfigDict(frozen=True)
