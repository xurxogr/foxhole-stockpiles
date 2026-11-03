"""Discord webhook connector."""

import asyncio
import json
import logging
import math
from typing import Any, Final

import httpx

from foxhole_stockpiles.connectors.discord_send_error import DiscordSendError
from foxhole_stockpiles.connectors.webhook import async_retry_on_connect_timeout

MAX_ATTACHMENTS: Final[int] = 10
MAX_CONTENT_CHARS: Final[int] = 2000

_MAX_RATE_LIMIT_RETRIES: Final[int] = 3
_MAX_WAIT_SECONDS: Final[float] = 30.0
_DEFAULT_RETRY_SECONDS: Final[float] = 1.0
_MAX_ERROR_CHARS: Final[int] = 200
_TIMEOUT_SECONDS: Final[float] = 60.0
_HTTP_TOO_MANY_REQUESTS: Final[int] = 429

logger = logging.getLogger(__name__)


def _seconds(value: Any) -> float | None:
    """Read a number of seconds sent by the server.

    Args:
        value (Any): The value of a header or JSON field.

    Returns:
        float | None: The seconds, or None if it is not a usable number.
    """
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _json_field(response: httpx.Response, field: str) -> Any:
    """Read a field of a JSON answer, which Discord's proxy does not always send.

    Args:
        response (httpx.Response): The answer.
        field (str): The name of the field.

    Returns:
        Any: Its value, or None if there is no such field.
    """
    try:
        data = response.json()
    except ValueError:
        return None
    return data.get(field) if isinstance(data, dict) else None


def _retry_delay(response: httpx.Response) -> float:
    """Read how long a rate limit asks to wait.

    Args:
        response (httpx.Response): The answer with the rate limit.

    Returns:
        float: The seconds to wait.
    """
    header = _seconds(response.headers.get("Retry-After"))
    if header is not None:
        return header
    field = _seconds(_json_field(response=response, field="retry_after"))
    return field if field is not None else _DEFAULT_RETRY_SECONDS


class DiscordConnector:
    """Posts images to a Discord webhook.

    It never logs the URL or quotes it in an error, as it holds the credential of the
    webhook. Mentions never notify anyone, as stockpile names are written by players.
    """

    def __init__(
        self, url: str, username: str | None = None, avatar_url: str | None = None
    ) -> None:
        """Initialize the connector.

        Args:
            url (str): The URL of the webhook.
            username (str | None): The name to post with.
            avatar_url (str | None): The avatar to post with.
        """
        self._url = url
        self._identity = {
            key: value
            for key, value in (("username", username), ("avatar_url", avatar_url))
            if value
        }
        self._client = httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)

    async def send_images(self, content: str | None, images: list[bytes]) -> None:
        """Post some images, in as many messages as they need.

        Args:
            content (str | None): The text of the first message.
            images (list[bytes]): The PNG images.

        Raises:
            DiscordSendError: If Discord did not accept a message.
        """
        text = (content or "")[:MAX_CONTENT_CHARS]
        for start in range(0, len(images), MAX_ATTACHMENTS):
            await self._post_message(
                content=text if start == 0 else "",
                images=images[start : start + MAX_ATTACHMENTS],
            )

    async def _post_message(self, content: str, images: list[bytes]) -> None:
        """Post one message, waiting out the rate limits that are short enough.

        Args:
            content (str): Its text.
            images (list[bytes]): Its images.

        Raises:
            DiscordSendError: If Discord did not accept it.
        """
        payload = {**self._identity, "content": content, "allowed_mentions": {"parse": []}}
        data = {"payload_json": json.dumps(payload)}
        files = [
            (f"files[{index}]", (f"stockpile_{index + 1}.png", image, "image/png"))
            for index, image in enumerate(images)
        ]
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            response = await self._request(data=data, files=files)
            if response.status_code != _HTTP_TOO_MANY_REQUESTS:
                break
            delay = _retry_delay(response)
            if delay > _MAX_WAIT_SECONDS or attempt == _MAX_RATE_LIMIT_RETRIES:
                raise DiscordSendError(f"Discord is rate limiting for {delay:.0f} more seconds")
            logger.info("Discord asked to wait %.1f seconds", delay)
            await asyncio.sleep(delay)

        if not response.is_success:
            reason = str(_json_field(response=response, field="message") or "")
            raise DiscordSendError(
                f"Discord answered HTTP {response.status_code}: {reason[:_MAX_ERROR_CHARS]}"
            )
        await self._respect_rate_limit(response)

    async def _request(self, data: dict[str, str], files: list[Any]) -> httpx.Response:
        """Make the request, hiding the errors that could quote the URL.

        Args:
            data (dict[str, str]): The form fields.
            files (list[Any]): The attachments.

        Returns:
            httpx.Response: The answer.

        Raises:
            DiscordSendError: If there was no answer.
        """
        try:
            return await self._post(data=data, files=files)
        except httpx.HTTPError as e:
            raise DiscordSendError(f"Could not reach Discord ({type(e).__name__})") from None

    @async_retry_on_connect_timeout(max_retries=3, delay=2)
    async def _post(self, data: dict[str, str], files: list[Any]) -> httpx.Response:
        """Send the request. ``wait`` makes Discord confirm the message was created.

        Args:
            data (dict[str, str]): The form fields.
            files (list[Any]): The attachments.

        Returns:
            httpx.Response: The answer.
        """
        return await self._client.post(
            url=self._url, params={"wait": "true"}, data=data, files=files
        )

    async def _respect_rate_limit(self, response: httpx.Response) -> None:
        """Wait if that was the last message allowed for now, to avoid a 429.

        Args:
            response (httpx.Response): The answer to the message.
        """
        if response.headers.get("X-RateLimit-Remaining") != "0":
            return
        delay = _seconds(response.headers.get("X-RateLimit-Reset-After"))
        if delay:
            await asyncio.sleep(min(delay, _MAX_WAIT_SECONDS))

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
