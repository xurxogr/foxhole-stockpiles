"""Discord send error."""


class DiscordSendError(RuntimeError):
    """Raised when Discord did not accept a message. Its text never holds the webhook URL."""
