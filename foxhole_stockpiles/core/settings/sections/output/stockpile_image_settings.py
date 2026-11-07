"""Settings shared by the handlers that draw stockpiles as images."""

from pydantic import BaseModel, ConfigDict, Field


class StockpileImageSettings(BaseModel):
    """How a stockpile is drawn.

    These belong to each handler, so two outputs can show the same data differently,
    for example with the icons of a different mod.
    """

    icon_mod: str = Field(
        description=("Mod of the template database whose icons replace those of the base game"),
        default="vanilla",
    )
    font_path: str | None = Field(
        description="Font tried before the ones of the system",
        default=None,
    )
    language: str = Field(
        description=(
            "Language of the text of the image, which can differ from the one of the "
            "window. Items the game has no translation for keep their English name"
        ),
        default="en",
    )
    model_config = ConfigDict(extra="forbid")
