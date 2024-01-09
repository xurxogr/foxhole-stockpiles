from numpy import ndarray
from pydantic import BaseModel
from pydantic import Field

class StockpileItem(BaseModel):
    id: str | None = Field(description="Id of the item", default=None)
    image: ndarray | None = Field(description="Image with the icon", default=None)
    quantity: int = Field(description="Quantity of the item", ge=-1, default=-1)
    threshold: float | None = Field(description="threshold for icon matching", deffault=None)

    class Config:
        arbitrary_types_allowed=True
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "id": "34",
                "image": [],
                "quantity": 30
            }
        }
