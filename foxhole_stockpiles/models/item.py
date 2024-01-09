from numpy import ndarray
from pydantic import BaseModel
from pydantic import Field

class Item(BaseModel):
    id: str | None = Field(description="Id of the item", default=None)
    image: ndarray | None = Field(description="Image with the icon", default=None)
    # FIXME: Load the rest of properties (type, name, description, cost, etc)

    class Config:
        arbitrary_types_allowed=True
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "id": "34",
                "image": [],
            }
        }
