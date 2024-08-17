from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.catalog_item_category import catalog_item_category


class CatalogItem(BaseModel):
    code: str = Field(description="Code of the item")
    display: str = Field(description="Display name for the item")
    description: str = Field(description="Item in game description")
    category: catalog_item_category | None = Field(description="Item category for displaying ingame", default=None)
    # TODO: Load the rest of the properties

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "code": "rifle",
                "display": "Rifle",
                "description": "A rifle",
                "category": catalog_item_category.SMALL_ARMS
            }
        }
    )
