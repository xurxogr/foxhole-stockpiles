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
    template_cache_size: int = Field(
        description=(
            "Maximum number of resolution databases to cache in memory (LRU cache). "
            "0 = No caching (load from disk each time, minimal memory ~150-200 MB). "
            "1 = Cache only last used resolution (good for single-resolution servers). "
            "2-4 = Cache a few common resolutions (balanced approach). "
            "16 = Cache all resolutions (maximum performance, ~200-250 MB). "
            "Each cached resolution uses ~5-15 MB depending on template count and image size."
        ),
        default=16,
        ge=0,
    )
    early_exit_threshold: float = Field(
        description=(
            "Early exit threshold for icon matching. "
            "If a match with confidence >= this threshold is found, stop testing other candidates. "
            "Set to 0.0 to disable early exit and test all candidates."
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
    debug_mode: bool = Field(description="Enable debug mode to save debug images", default=False)
    extract_icons: bool = Field(
        description="Extract detected icons to 'icons' folder for debugging (<index>_<code>.png)",
        default=False,
    )
    screenshots_folder: str = Field(
        description="Folder to save screenshots before processing. Empty string disables saving.",
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
                "template_cache_size": 16,
                "early_exit_threshold": 0.0,
                "confidence_gap": 0.0,
                "debug_mode": False,
                "extract_icons": False,
                "screenshots_folder": "screenshots",
            }
        },
    )
