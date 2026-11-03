"""Settings shared by the handlers that draw stockpiles as images."""

from pydantic import BaseModel, ConfigDict, Field


class StockpileImageSettings(BaseModel):
    """How a stockpile is drawn.

    These belong to each handler, so two outputs can show the same data differently,
    for example with the icons of a different mod.
    """

    headline: str | None = Field(
        description=(
            "Title of the image, by default the name of the stockpile. Supports the "
            "placeholders {name}, {type}, {hex}, {shard}, {ingame_timestamp}, "
            "{timestamp}, {resolution}, {item_count} and {total_items}"
        ),
        default=None,
    )
    icon_mod: str = Field(
        description=("Mod of the template database whose icons replace those of the base game"),
        default="vanilla",
    )
    font_path: str | None = Field(
        description="Font tried before the ones of the system",
        default=None,
    )
    aggregate: bool = Field(
        description="Draw all the stockpiles of a batch as one, adding up their items",
        default=False,
    )

    model_config = ConfigDict(extra="forbid")
