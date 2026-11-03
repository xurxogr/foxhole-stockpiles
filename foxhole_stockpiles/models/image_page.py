"""One page of a stockpile image."""

from pydantic import BaseModel, ConfigDict

from foxhole_stockpiles.models.image_line import ImageLine


class ImagePage(BaseModel):
    """The columns of lines drawn in one image.

    Attributes:
        columns (list[list[ImageLine]]): The lines of each column, left to right.
    """

    model_config = ConfigDict(frozen=True)

    columns: list[list[ImageLine]]
