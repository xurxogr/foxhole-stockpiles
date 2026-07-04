"""SAV processing settings."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.sav_mode import SavMode


class SavProcessingSettings(BaseModel):
    """Settings for SAV file processing.

    These settings configure how the application handles Foxhole save files
    for stockpile data extraction.
    """

    mode: SavMode = Field(
        description=(
            "SAV control mode for the main window. 'manual' uses a hotkey to scan "
            "the .sav once per press; 'monitor' auto-polls the .sav for changes."
        ),
        default=SavMode.MANUAL,
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
        ge=0.1,
        le=60.0,
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
