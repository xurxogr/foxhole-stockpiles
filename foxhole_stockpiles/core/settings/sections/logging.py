"""Logging settings."""

from pydantic import BaseModel, ConfigDict, Field


class LoggingSettings(BaseModel):
    """Settings for logging."""

    loggers: dict[str, str] = Field(description="Loggers and their levels", default_factory=dict)
    log_level: str = Field(description="Logging level", default="INFO")
    log_format: str = Field(
        description="Logging format",
        default="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    )
    date_format: str = Field(description="Logging date format", default="%Y-%m-%d %H:%M:%S")
    rotate_logs: bool = Field(description="Rotate logs daily", default=False)
    log_file: str | None = Field(description="Log file to write to", default=None)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "loggers": {"foxhole_stockpiles": "DEBUG", "httpx": "WARNING"},
                "log_level": "INFO",
                "log_format": "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
                "rotate_logs": False,
                "log_file": None,
            }
        },
    )
