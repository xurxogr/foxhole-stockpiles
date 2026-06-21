"""Scanner settings."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ScannerSettings(BaseModel):
    """Configuration for stockpile analysis."""

    database_path: Path | None = Field(
        description=(
            "Path to the template database file. Optional for commands that don't use templates."
        ),
        default=None,
    )
    capture_key: str | None = Field(
        description=(
            "Global hotkey that captures the Foxhole window and scans it (e.g. 'F9'). "
            "When unset, screenshot capture is disabled until a key is configured."
        ),
        default=None,
    )
    early_exit_threshold: float = Field(
        description=(
            "Early exit threshold for icon matching (used by fs-tools' candidate "
            "inspector). If a match with confidence >= this threshold is found, stop "
            "testing other candidates. Set to 0.0 to disable early exit."
        ),
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    confidence_gap: float = Field(
        description=(
            "Confidence gap for returning alternative candidates. "
            "If set > 0.0, returns candidates within (best_confidence - confidence_gap) range. "
            "These candidates must have the same category, crated status, and mod as the "
            "best match. Set to 0.0 to disable candidate reporting."
        ),
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    screenshots_folder: str = Field(
        description=(
            "Folder to save captured screenshots. When set, each screenshot taken "
            "via the capture hotkey is saved here (in a per-day subfolder). "
            "Empty string disables saving."
        ),
        default="",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "database_path": "database.h5",
                "capture_key": "F9",
                "early_exit_threshold": 0.0,
                "confidence_gap": 0.0,
                "screenshots_folder": "screenshots",
            }
        },
    )
