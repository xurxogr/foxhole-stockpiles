from pydantic import BaseModel

from foxhole_stockpiles.models.enums.catalog_item_category import catalog_item_category


class CatalogItem(BaseModel):
    code: str
    display: str
    description: str
    category: catalog_item_category | None

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
