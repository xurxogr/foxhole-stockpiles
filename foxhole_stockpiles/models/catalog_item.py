from pydantic import BaseModel
from pydantic import Field

from foxhole_stockpiles.models.enums.catalog_item_category import catalog_item_category


class CatalogItem(BaseModel):
    code: str = Field(description="Code of the item")
    display: str = Field(description="Display name for the item")
    description: str = Field(description="Item in game description")
    category: catalog_item_category | None = Field(description="Item category for displaying ingame", default=None)
    # TODO: Load the rest of the properties

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "code": "GrenadeLauncherC",
                "display": "KLG901-2 Lunaire F",
                "description": "A weapon designed to launch specialty grenades over long-distances.  This modern Kraunian firearm uses advanced propulsion designed for increased efficiency due to the overall weight of the weapon and projectiles. ",
                "category": catalog_item_category.HEAVY_ARMS.value
            }
        }
