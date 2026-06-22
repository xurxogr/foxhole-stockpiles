"""Result model for mod import operations."""

from pydantic import BaseModel, ConfigDict, Field


class ModImportResult(BaseModel):
    """Result of mod import operation."""

    success: bool = Field(default=False, description="Whether the import completed successfully")
    templates_added: int = Field(default=0, description="Number of new templates added")
    templates_skipped: int = Field(
        default=0, description="Number of templates skipped (already in database)"
    )
    error_message: str = Field(default="", description="Error message if success is False")
    warnings: list[str] = Field(default_factory=list, description="List of warning messages")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )
