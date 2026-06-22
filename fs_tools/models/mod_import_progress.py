"""Progress model for mod import operations."""

from pydantic import BaseModel, ConfigDict, Field


class ModImportProgress(BaseModel):
    """Progress information for mod import operation."""

    current_step: int = Field(default=0, description="Current step number (0-4)")
    total_steps: int = Field(default=4, description="Total number of steps")
    step_name: str = Field(default="", description="Name of current step")
    message: str = Field(default="", description="Detailed progress message")
    is_complete: bool = Field(default=False, description="Whether import is complete")
    is_error: bool = Field(default=False, description="Whether an error occurred")
    error_message: str = Field(default="", description="Error message if is_error is True")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )
