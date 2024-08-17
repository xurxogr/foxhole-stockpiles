from numpy import ndarray
from pydantic import BaseModel, ConfigDict, Field


class StockpileItem(BaseModel):
    code: str = Field(description="Code of item detected from the icon")
    icon_image: ndarray | None = Field(description="Icon image", default=None, exclude=True)
    quantity: int = Field(description="Quantity of the item", ge=-1, default=-1)
    quantity_image: ndarray | None = Field(description="Quantity image", default=None, exclude=True)
    crated: bool = Field(description="Is the item crated?", default=False)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "code": "GrenadeLauncherC",
                "quantity": 3,
                "crated": False
            }
        }
    )
