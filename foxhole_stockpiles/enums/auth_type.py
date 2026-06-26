"""Enums for authentication types."""

from enum import StrEnum


class AuthType(StrEnum):
    """Supported authentication types."""

    BASIC = "basic"
    BEARER = "bearer"
    HEADER = "header"
