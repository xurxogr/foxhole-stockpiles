"""Template settings."""

from pydantic import BaseModel, ConfigDict, Field


class TemplateSettings(BaseModel):
    """Settings for the template generation."""

    crate_blue_multiplier: int = Field(
        description=(
            "Multiplier for blue channel when applying crate color tint "
            "(0-255, will be divided by 255)"
        ),
        ge=0,
        le=255,
        default=145,
    )
    crate_blue_offset: int = Field(
        description="Offset for blue channel when applying crate color tint",
        ge=0,
        le=255,
        default=82,
    )
    crate_green_multiplier: int = Field(
        description=(
            "Multiplier for green channel when applying crate color tint "
            "(0-255, will be divided by 255)"
        ),
        ge=0,
        le=255,
        default=152,
    )
    crate_green_offset: int = Field(
        description="Offset for green channel when applying crate color tint",
        ge=0,
        le=255,
        default=87,
    )
    crate_red_multiplier: int = Field(
        description=(
            "Multiplier for red channel when applying crate color tint "
            "(0-255, will be divided by 255)"
        ),
        ge=0,
        le=255,
        default=154,
    )
    crate_red_offset: int = Field(
        description="Offset for red channel when applying crate color tint",
        ge=0,
        le=255,
        default=89,
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "crate_blue_multiplier": 145,
                "crate_blue_offset": 82,
                "crate_green_multiplier": 152,
                "crate_green_offset": 87,
                "crate_red_multiplier": 154,
                "crate_red_offset": 89,
            }
        },
    )
