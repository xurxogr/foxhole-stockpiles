"""SAV processing settings."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.core.constants import MAX_POLL_INTERVAL, MIN_POLL_INTERVAL
from foxhole_stockpiles.enums.capture_mode import CaptureMode


class SavProcessingSettings(BaseModel):
    """Settings for SAV file processing.

    These settings configure how the application handles Foxhole save files
    for stockpile data extraction.
    """

    mode: CaptureMode = Field(
        description=(
            "SAV control mode for the main window. 'manual' uses a hotkey to scan "
            "the .sav once per press; 'monitor' auto-polls the .sav for changes."
        ),
        default=CaptureMode.MANUAL,
    )
    sav_capture_key: str | None = Field(
        description=(
            "Global hotkey that scans the configured .sav file once (e.g. 'F10'), "
            "used in manual mode. When unset, SAV hotkey scanning is disabled."
        ),
        default=None,
    )
    sav_file_path: Path | None = Field(
        description="Path to the Foxhole save file (.sav) to process",
        default=None,
    )
    poll_interval: float = Field(
        description="Polling interval in seconds for monitoring mode",
        default=1.0,
        ge=MIN_POLL_INTERVAL,
        le=MAX_POLL_INTERVAL,
    )
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "mode": "manual",
                "sav_file_path": (
                    "C:/Users/User/AppData/Local/Foxhole/Saved/SaveGames/User_MapData.sav"
                ),
                "poll_interval": 1.0,
            }
        },
    )
