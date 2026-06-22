"""Match result models for template matching operations."""

from pydantic import BaseModel, ConfigDict, Field

from fs_tools.models.icon_template import IconTemplate


class MatchResult(BaseModel):
    """Complete result of candidate filtering and optional icon matching."""

    candidates: list[int] = Field(description="List of candidate template indices")
    icon: IconTemplate | None = Field(
        description=(
            "Matched IconTemplate if icon_image was provided and match found, None otherwise"
        ),
        default=None,
    )
    confidence: float | None = Field(
        description="Confidence score of the icon match, None if no icon matching performed",
        default=None,
    )
    best_match: IconTemplate | None = Field(
        description=(
            "Best matching template even if below confidence threshold. "
            "Useful for debugging and error reporting."
        ),
        default=None,
    )
    best_confidence: float = Field(
        description="Confidence score of the best match, regardless of threshold",
        default=0.0,
    )
    tested_candidates: int = Field(
        description="Number of candidates that were tested during icon matching",
        default=0,
    )
    top_matches: list[tuple[IconTemplate, float]] = Field(
        description="List of top N matches with their confidence scores (template, confidence)",
        default_factory=list,
    )
    gap_candidates: list[tuple[IconTemplate, float]] = Field(
        description=(
            "Alternative candidates within the confidence gap. "
            "Only includes items with the same category, crated status, and mod as the best match. "
            "Empty if confidence_gap is 0.0 or no alternatives exist."
        ),
        default_factory=list,
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "candidates": [0, 15, 42],
                "icon": {
                    "code": "Rifle",
                    "crated": False,
                    "faction": "neutral",
                    "category": "item",
                    "mod": "vanilla",
                    "resolution": "1080",
                },
                "confidence": 0.8756,
                "tested_candidates": 50,
            }
        },
    )
