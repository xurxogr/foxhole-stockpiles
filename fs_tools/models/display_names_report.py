"""What importing the display names changed."""

from pydantic import BaseModel, ConfigDict


class DisplayNamesReport(BaseModel):
    """The result of importing the names of the stockpile types."""

    languages: list[str]
    imported: int
    not_in_enum: list[str]

    model_config = ConfigDict(frozen=True)
