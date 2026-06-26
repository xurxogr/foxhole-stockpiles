"""Webhook connector."""

import functools
import logging
from asyncio import sleep
from collections.abc import Callable
from typing import Any, Final, TypeVar

import httpx
from httpx import AsyncClient, ConnectTimeout

from foxhole_stockpiles.core.settings.sections.output import WebhookHandlerSettings
from foxhole_stockpiles.enums.auth_type import AuthType

F = TypeVar("F", bound=Callable[..., Any])


def async_retry_on_connect_timeout(max_retries: int = 3, delay: int = 1) -> Callable[[F], F]:
    """Retry a function if a ConnectTimeout exception is raised.

    This decorator will automatically retry the decorated function if it raises
    a ConnectTimeout exception, with a maximum number of retries and a specified
    delay between retries.

    Args:
        max_retries (int): Maximum number of retries. Default is 3
        delay (int): Delay between retries. Default is 1

    Returns:
        Callable[[F], F]: Decorated function

    Raises:
        ValueError: If max_retries is not a positive integer
        TypeError: If delay is not an integer
    """
    if max_retries <= 0:
        raise ValueError("max_retries must be a positive integer.")

    def decorator(func: F) -> F:
        """Decorator function to retry the decorated function.

        Args:
            func (F): Function to decorate

        Returns:
            F: Decorated function
        """

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper function to retry the decorated function.

            Args:
                *args: Positional arguments
                **kwargs: Keyword arguments

            Returns:
                Any: Result of the decorated function
            """
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except ConnectTimeout as e:
                    retries += 1
                    if retries == max_retries:
                        raise e

                    logger = logging.getLogger(__name__)
                    logger.info(
                        "ConnectTimeout occurred. Retrying (%d/%d)...", retries, max_retries
                    )
                    await sleep(delay)
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


class WebhookConnector:
    """Webhook connector class."""

    DEFAULT_MESSAGE_EMPTY: Final[str] = "FS: Stockpile is Empty"
    DEFAULT_MESSAGE_NO_URL: Final[str] = "FS: Webhook URL is not set"
    DEFAULT_ERROR_PREFIX: Final[str] = "FS: Error sending stockpile to the webhook"

    def __init__(self, output_settings: WebhookHandlerSettings) -> None:
        """Initialize the WebhookConnector.

        Args:
            output_settings (WebhookHandlerSettings): Webhook configuration
        """
        self._output_settings = output_settings
        self._logger = logging.getLogger(__name__)
        self._client = AsyncClient(timeout=30.0)

    def _build_auth_headers(self, token: str | None = None) -> dict[str, str]:
        """Build authentication headers based on configured auth method.

        Args:
            token (str | None): Optional token to override the configured webhook token

        Returns:
            dict[str, str]: Headers dictionary with appropriate authentication credentials
        """
        headers: dict[str, str] = {}

        auth_type = self._output_settings.auth_type

        if auth_type is None:
            return headers

        match auth_type:
            case AuthType.BASIC:
                token_to_use = token or self._output_settings.token
                if token_to_use:
                    headers["Authorization"] = f"Basic {token_to_use}"
            case AuthType.BEARER:
                token_to_use = token or self._output_settings.token
                if token_to_use:
                    headers["Authorization"] = f"Bearer {token_to_use}"
            case AuthType.HEADER:
                # The configured token is placed verbatim in a user-chosen header.
                if self._output_settings.auth_header and self._output_settings.token:
                    headers[self._output_settings.auth_header] = self._output_settings.token

        return headers

    @async_retry_on_connect_timeout(max_retries=3, delay=2)
    async def send_stockpile(
        self, payload: dict[str, Any], token: str | None = None
    ) -> dict[str, str]:
        """Send stockpile data to the configured webhook endpoint.

        Args:
            payload (dict[str, Any]): Stockpile data dictionary to send to the webhook
            token (str | None): Optional token to override the configured webhook token

        Returns:
            dict[str, str]: Response dictionary from the webhook or error message

        Raises:
            ConnectTimeout: If the connection times out after maximum retry attempts
        """
        if not payload:
            return {"message": self.DEFAULT_MESSAGE_EMPTY}

        if not self._output_settings.url:
            self._logger.info("Webhook URL is not configured")
            return {"message": self.DEFAULT_MESSAGE_NO_URL}

        headers = self._build_auth_headers(token)
        return_data: dict[str, str] = {}

        try:
            response = await self._client.post(
                url=self._output_settings.url, json=payload, headers=headers
            )

            try:
                response.raise_for_status()
                res_data = response.json()
                return_data = res_data.get("error", res_data.get("message", res_data))
            except httpx.HTTPStatusError as e:
                return {"message": f"HTTP {e.response.status_code} error from server"}
            except ValueError:
                return {"message": f"HTTP {response.status_code}: {response.text}"}
        except ConnectTimeout:
            raise
        except Exception as e:
            error_message = f"{self.DEFAULT_ERROR_PREFIX}: ({type(e).__name__}, {str(e)})"
            self._logger.error(error_message)
            return_data = {"message": error_message}

        return return_data

    async def close(self) -> None:
        """Close the persistent HTTP client.

        This should be called when the connector is no longer needed to free resources.
        """
        if not self._client.is_closed:
            await self._client.aclose()
