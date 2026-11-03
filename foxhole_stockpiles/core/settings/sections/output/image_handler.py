"""Image handler settings."""

from pydantic import Field

from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType


class ImageHandlerSettings(StockpileImageSettings):
    """Settings for the handler that saves stockpiles as PNG files."""

    type: OutputHandlerType = Field(default=OutputHandlerType.IMAGE, description="Handler type")
    path: str = Field(
        description=(
            "Path of the image of each stockpile. Supports the placeholders of the file "
            "handler. Its extension is always .png"
        ),
        default="{timestamp}_{stockpile_name}.png",
    )
