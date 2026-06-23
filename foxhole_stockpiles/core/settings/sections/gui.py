"""GUI settings."""

from pydantic import BaseModel, ConfigDict, Field


class GUISettings(BaseModel):
    """Settings for the GUI."""

    minimize_to_tray: bool = Field(
        description="Minimize to system tray instead of quitting when closing the window",
        default=False,
    )
    language: str = Field(
        description="Language code for the GUI (e.g., 'en', 'es', 'de')",
        default="en",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "minimize_to_tray": False,
                "language": "en",
            }
        },
    )
