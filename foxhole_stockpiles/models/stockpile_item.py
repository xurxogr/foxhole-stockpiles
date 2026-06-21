"""Stockpile item model."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_serializer

from foxhole_stockpiles.models.item_candidate import ItemCandidate


class StockpileItem(BaseModel):
    """Stockpile item model."""

    code: str = Field(description="Code of item detected from the icon")
    quantity: int = Field(description="Quantity of the item", ge=-1, default=-1)
    crated: bool = Field(description="Is the item crated?", default=False)
    confidence: float | None = Field(
        description="Confidence of the item detection",
        ge=0.0,
        le=1.0,
        default=None,
    )
    x: int | None = Field(
        description=(
            "X pixel coordinate of the item's icon in the source screenshot. "
            "Populated when the stockpile comes from an OCR scan; None for other "
            "sources (e.g. .sav files)."
        ),
        default=None,
    )
    y: int | None = Field(
        description=(
            "Y pixel coordinate of the item's icon in the source screenshot. "
            "Populated when the stockpile comes from an OCR scan; None for other "
            "sources (e.g. .sav files)."
        ),
        default=None,
    )
    candidates: list[ItemCandidate] | None = Field(
        description=(
            "Alternative candidates within the confidence gap. "
            "Only included if confidence_gap > 0 and alternatives exist. "
            "Candidates have the same category, crated status, and mod as the matched item."
        ),
        default=None,
        exclude=True,  # Exclude from default serialization, handle in model_serializer
    )

    @field_serializer("confidence")
    def serialize_confidence(self, value: float | None) -> float | None:
        """Serialize confidence to 3 decimal places.

        Args:
            value (float | None): Confidence value

        Returns:
            float | None: Rounded confidence value
        """
        if value is None:
            return None
        return round(value, 3)

    @model_serializer(mode="wrap")
    def serialize_model(self, serializer: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
        """Custom serializer to conditionally include candidates field.

        Args:
            serializer: The default serializer function

        Returns:
            dict: Serialized model data
        """
        data: dict[str, Any] = serializer(self)

        # Add candidates only if not None and not empty
        if self.candidates:
            data["candidates"] = [
                {"code": c.code, "confidence": round(c.confidence, 3)} for c in self.candidates
            ]

        return data

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "code": "GrenadeLauncherC",
                "quantity": 3,
                "crated": False,
                "confidence": 0.95,
                "candidates": [
                    {"code": "GrenadeLauncherW", "confidence": 0.92},
                    {"code": "GrenadeLauncher", "confidence": 0.90},
                ],
            }
        },
    )
