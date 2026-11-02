"""Error raised when Google credentials cannot be obtained."""


class CredentialsUnavailableError(RuntimeError):
    """Raised when no usable Google credentials can be obtained."""
