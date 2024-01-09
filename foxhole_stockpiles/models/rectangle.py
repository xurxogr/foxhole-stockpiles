from pydantic import BaseModel
from pydantic import Field


class Rectangle(BaseModel):
    x: int = Field(description="Coordinate X of the rectangle", ge=0)
    y: int = Field(description="Coordinate Y of the rectangle", ge=0)
    width: int = Field(description="Width of the rectangle", gt=0)
    height: int = Field(description="Height of the rectangle", gt=0)

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "x": 10,
                "y": 25,
                "width": 60,
                "height": 40
            }
        }
