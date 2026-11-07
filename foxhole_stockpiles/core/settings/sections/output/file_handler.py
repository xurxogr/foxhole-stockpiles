"""File handler settings."""

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType


class FileHandlerSettings(BaseModel):
    """Settings for file output handler."""

    type: OutputHandlerType = Field(default=OutputHandlerType.FILE, description="Handler type")
    path: str = Field(
        description=(
            "Path to the output file. Supports placeholders: "
            "{timestamp}, {year}, {month}, {day}, {hour}, {minute}, {second}, "
            "{type}, {name}, {hex}, {resolution}"
        ),
        default="output.json",
    )

    model_config = ConfigDict(extra="forbid")
