"""Discord handler settings."""

import re
from typing import Final

from pydantic import ConfigDict, Field

from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType

# The URL holds the credential of the webhook, so it only ever goes to Discord.
_WEBHOOK_URL: Final[re.Pattern[str]] = re.compile(
    r"https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/\d+/[\w-]+/?"
)


def is_discord_webhook_url(url: str) -> bool:
    """Check that a URL is a webhook of Discord.

    The settings accept any text, so that a wrong URL does not invalidate the whole
    configuration. This is checked when typing it and before sending anything.

    Args:
        url (str): The URL.

    Returns:
        bool: Whether stockpiles can be sent to it.
    """
    return _WEBHOOK_URL.fullmatch(url) is not None


class DiscordHandlerSettings(StockpileImageSettings):
    """Settings for the handler that posts stockpiles as images to a Discord webhook."""

    type: OutputHandlerType = Field(default=OutputHandlerType.DISCORD, description="Handler type")
    url: str = Field(description="URL of the Discord webhook", default="", repr=False)
    username: str | None = Field(
        description="Name to post with, by default the one of the webhook", default=None
    )
    avatar_url: str | None = Field(
        description="Avatar to post with, by default the one of the webhook", default=None
    )
    message: str | None = Field(
        description=(
            "Text posted with the images of each stockpile. Supports the same "
            "placeholders as the headline. Mentions in it do not notify anyone"
        ),
        default=None,
    )

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
