"""Webhook handler settings."""

from typing import ClassVar, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType


class WebhookHandlerSettings(BaseModel):
    """Settings for webhook output handler."""

    type: OutputHandlerType = Field(default=OutputHandlerType.WEBHOOK, description="Handler type")
    url: str | None = Field(description="Webhook URL for sending output", default=None)
    auth_type: AuthType | None = Field(
        description=(
            "Authentication type to use when sending to webhook. "
            "Supported types: 'basic', 'bearer', or 'header'."
        ),
        default=None,
    )
    token: str | None = Field(
        description=(
            "Token to use for authentication when sending to webhook. "
            "For 'basic' auth_type, this should be base64 encoded 'username:password'. "
            "Required when auth_type is 'basic', 'bearer', or 'header'."
        ),
        default=None,
    )
    auth_header: str | None = Field(
        description=(
            "Name of the header to place the token in. Required when auth_type is 'header'."
        ),
        default=None,
    )

    model_config = ConfigDict(extra="forbid")

    ALLOWED_URL_SCHEMES: ClassVar[frozenset[str]] = frozenset({"http", "https"})

    @model_validator(mode="after")
    def validate_auth_consistency(self) -> Self:
        """Validate that webhook auth type and token are consistent.

        Returns:
            Self: The validated instance.

        Raises:
            ValueError: If webhook auth configuration is invalid.
        """
        auth = self.auth_type
        if auth in (AuthType.BASIC, AuthType.BEARER):
            if not self.token:
                raise ValueError(f"token must be set when auth_type is '{auth}'")
        elif auth == AuthType.HEADER:
            if not self.token:
                raise ValueError("token must be set when auth_type is 'header'")
            if not self.auth_header:
                raise ValueError("auth_header must be set when auth_type is 'header'")
        return self

    @model_validator(mode="after")
    def validate_url_scheme(self) -> Self:
        """Validate that the webhook URL uses an allowed scheme.

        Returns:
            Self: The validated instance.

        Raises:
            ValueError: If the URL scheme is not http or https.
        """
        if self.url:
            scheme = urlsplit(self.url).scheme.lower()
            if scheme not in self.ALLOWED_URL_SCHEMES:
                raise ValueError(
                    f"Webhook URL scheme '{scheme}' is not allowed; "
                    f"must be one of {sorted(self.ALLOWED_URL_SCHEMES)}"
                )
        return self
