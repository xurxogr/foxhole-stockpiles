"""Settings shared by the handlers that draw stockpiles as images."""

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping


class StockpileImageSettings(BaseModel):
    """How a stockpile is drawn.

    These belong to each handler, so two outputs can show the same data differently,
    for example with the icons of a different mod.
    """

    headline: str | None = Field(
        description=(
            "Title of each image that merges stockpiles, by default what they share; "
            "one stockpile shows its type and name. Supports the "
            "placeholders {name}, {type}, {hex}, {ingame_timestamp}, "
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
    language: str = Field(
        description=(
            "Language of the text of the image, which can differ from the one of the "
            "window. Items the game has no translation for keep their English name"
        ),
        default="en",
    )
    grouping: StockpileGrouping = Field(
        description=(
            "Which stockpiles of a send are drawn as one, adding up their items: none, "
            "all, those of one hex, or those of one place (same coordinates)"
        ),
        default=StockpileGrouping.NONE,
    )

    model_config = ConfigDict(extra="forbid")
