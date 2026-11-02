"""Catalog code model."""

from pydantic import BaseModel, ConfigDict

from foxhole_stockpiles.enums.item_faction import ItemFaction


class CatalogCode(BaseModel):
    """A catalog item's code and faction, used for clipboard code-mapping."""

    code: str
    faction: ItemFaction

    model_config = ConfigDict(frozen=True)
