"""API settings."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from foxhole_stockpiles.enums.auth_type import AuthType


class APIServerSettings(BaseModel):
    """Settings for API server."""

    cors_allow_origins: list[str] = Field(
        description=(
            "List of allowed CORS origins. "
            "Use ['*'] to allow all origins (not recommended for production)."
        ),
        default_factory=list,
    )
    host: str = Field(
        description="Server bind host",
        default="127.0.0.1",
    )
    port: int = Field(
        description="Server bind port",
        default=8000,
        gt=0,
        le=65535,
    )
    workers: int = Field(
        description="Number of worker processes",
        default=1,
        gt=0,
    )
    max_concurrent_scans: int = Field(
        description=(
            "Maximum concurrent scan operations per worker. "
            "Limits CPU contention from parallel OCR/template matching. "
            "Effective system limit = workers × max_concurrent_scans. "
            "Set to 0 to disable (default). "
            "Recommended: workers=2, max_concurrent_scans=2 for 6-core systems."
        ),
        default=0,
        ge=0,
    )
    reload: bool = Field(
        description="Enable auto-reload on code changes (development only)",
        default=False,
    )
    log_level: str = Field(
        description="Server log level",
        default="info",
    )
    enable_memory_monitoring: bool = Field(
        description=(
            "Enable memory monitoring to track memory usage per request. "
            "When enabled, exposes /memory/* endpoints for statistics and provides "
            "automatic memory snapshots."
        ),
        default=False,
    )
    auto_trim_memory: bool = Field(
        description=(
            "Automatically call malloc_trim() after each scan request to release freed memory "
            "back to the operating system. This helps prevent memory fragmentation from keeping "
            "process memory high."
        ),
        default=True,
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "cors_allow_origins": ["https://yourdomain.com", "https://app.yourdomain.com"],
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 4,
                "max_concurrent_scans": 2,
                "reload": False,
                "log_level": "info",
                "enable_memory_monitoring": False,
                "auto_trim_memory": True,
            }
        },
    )


class APIAuthSettings(BaseModel):
    """Settings for API authentication."""

    auth_type: AuthType | None = Field(
        description=(
            "Authentication type to protect API endpoints. "
            "Supported types: 'basic' or 'bearer'. "
            "If None, authentication is disabled."
        ),
        default=None,
    )
    auth_token: str | None = Field(
        description=(
            "Token to use for API authentication. "
            "For 'basic' auth_type, this should be base64 encoded 'username:password'. "
            "Required when auth_type is set."
        ),
        default=None,
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "auth_type": "bearer",
                "auth_token": "your-secret-token",
            }
        },
    )

    def _validate_auth_consistency(self) -> None:
        """Validate that auth type and token are consistent.

        Raises:
            ValueError: If only one of auth_type or auth_token is provided.
        """
        if bool(self.auth_type) != bool(self.auth_token):
            raise ValueError("auth_type and auth_token must both be set or both be None")
        if self.auth_type == AuthType.FORWARD:
            raise ValueError("auth_type 'forward' is not supported for API authentication")

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        """Validate the model.

        Returns:
            Self: The validated instance.

        Raises:
            ValueError: If any of the fields is invalid
        """
        self._validate_auth_consistency()

        return self
