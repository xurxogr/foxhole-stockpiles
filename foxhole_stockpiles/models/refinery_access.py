"""Refinery access model."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from foxhole_stockpiles.enums.refinery_access_level import RefineryAccessLevel


class RefineryAccess(BaseModel):
    """Owner of a refinery order queue or storage."""

    level: RefineryAccessLevel = Field(description="Access level (personal, public or squad)")
    squad_id: int | None = Field(
        description="Squad id, only present when level is squad", default=None
    )

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: Any) -> Any:
        """Normalize string access levels, including in-game enum names.

        Args:
            value (Any): Raw level value.

        Returns:
            Any: The normalized access level, or the value untouched if not a string.
        """
        if isinstance(value, str):
            return RefineryAccessLevel.from_string(value)
        return value

    @model_validator(mode="after")
    def check_squad_id(self) -> Self:
        """Reject a squad id on a non-squad access level.

        Returns:
            Self: The validated model.

        Raises:
            ValueError: If squad_id is set and level is not squad.
        """
        if self.squad_id is not None and self.level != RefineryAccessLevel.SQUAD:
            raise ValueError(f"squad_id is only allowed with level 'squad', got '{self.level}'")
        return self

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "level": RefineryAccessLevel.SQUAD,
                "squad_id": 1,
            }
        },
    )
