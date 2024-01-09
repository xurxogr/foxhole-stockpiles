from numpy import ndarray
from pydantic import BaseModel
from pydantic import Field

class Image(BaseModel):
    name: str = Field(description="Name of the image")
    image: ndarray = Field(description="Image data")

    class Config:
        arbitrary_types_allowed = True
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "name": "Debug",
                "image": []
            }
        }
