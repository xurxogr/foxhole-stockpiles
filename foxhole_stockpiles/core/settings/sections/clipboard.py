"""Clipboard processing settings."""

from pydantic import BaseModel, ConfigDict, Field

from foxhole_stockpiles.enums.clip_mode import ClipMode


class ClipboardSettings(BaseModel):
    """Settings for clipboard stockpile-export processing.

    These configure how the application reads Foxhole's in-game "copy
    stockpile" clipboard exports and extracts stockpile data, mirroring the
    SAV processing controls.
    """

    mode: ClipMode = Field(
        description=(
            "Clipboard control mode for the main window. 'manual' uses a hotkey "
            "to read the clipboard once per press; 'monitor' auto-polls the "
            "clipboard and emits each new stockpile export."
        ),
        default=ClipMode.MANUAL,
    )
    clip_capture_key: str | None = Field(
        description=(
            "Global hotkey that reads the clipboard once (e.g. 'F11'), used in "
            "manual mode. When unset, clipboard hotkey reading is disabled."
        ),
        default=None,
    )
    poll_interval: float = Field(
        description="Polling interval in seconds for monitor mode",
        default=1.0,
        ge=0.1,
        le=60.0,
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "mode": "manual",
                "clip_capture_key": "F11",
                "poll_interval": 1.0,
            }
        },
    )
