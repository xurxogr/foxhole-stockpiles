"""This module contains the BackendConnector class.

The BackendConnector class is used to send stockpile information to the backend server.
"""

import functools
import logging
from asyncio import sleep
from typing import Any, Callable

from httpx import AsyncClient, ConnectTimeout


def async_retry_on_connect_timeout(max_retries: int = 3, delay: int = 1) -> Callable:
    """Retry a function if a ConnectTimeout exception is raised.

    This decorator will automatically retry the decorated function if it raises
    a ConnectTimeout exception, with a maximum number of retries and a specified
    delay between retries.

    Args:
        max_retries (int): Maximum number of retries. Default is 3
        delay (int): Delay between retries. Default is 1

    Returns:
        function: Decorated function

    Raises:
        ValueError: If max_retries is not a positive integer
        TypeError: If delay is not an integer
    """
    if not isinstance(max_retries, int) or max_retries <= 0:
        raise ValueError("max_retries must be a positive integer.")
    if not isinstance(delay, int):
        raise TypeError("delay must be an integer.")

    def decorator(func: Callable) -> Callable:
        """Decorator function to retry the decorated function.

        Args:
            func (Callable): Function to decorate

        Returns:
            Callable: Decorated function
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

        return wrapper

    return decorator


def async_retry_on_302(max_retries: int = 3, delay: int = 1) -> Callable:
    """Retry a function if a 302 status code is returned.

    This decorator will automatically retry the decorated function if the response
    status code is 302, with a maximum number of retries and a specified
    delay between retries.

    Args:
        max_retries (int): Maximum number of retries
        delay (int): Delay between retries

    Returns:
        function: Decorated function


    Raises:
        ValueError: If max_retries is not a positive integer
        TypeError: If delay is not an integer
    """
    if not isinstance(max_retries, int) or max_retries <= 0:
        raise ValueError("max_retries must be a positive integer.")
    if not isinstance(delay, int):
        raise TypeError("delay must be an integer.")

    def decorator(func: Callable) -> Callable:
        """Decorator function to retry the decorated function.

        Args:
            func (Callable): Function to decorate

        Returns:
            Callable: Decorated function
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
                response = await func(*args, **kwargs)
                if response.status_code != 302:
                    return response

                logger = logging.getLogger(__name__)
                logger.info("302 occurred. Retrying (%d/%d)...", retries, max_retries)
                await sleep(delay)
                retries += 1

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class BackendConnector:
    """Connector to the backend server."""

    def __init__(self, url: str):
        """Initialize the BackendConnector.

        Args:
            url (str): URL of the backend server
        """
        self.__url = url

    # @async_retry_on_302(max_retries=3, delay=2)
    @async_retry_on_connect_timeout(max_retries=3, delay=2)
    async def send_stockpile(self, payload: dict, api_key: str) -> dict:
        """Send an stockpile to the backend server.

        Args:
            payload (dict): Payload to send to the backend server
            api_key (str): API key to use for authentication

        Returns:
            dict: Response from the backend server

        Raises:
            ConnectTimeout: If the connection times out while sending the stockpile
                after the maximum number of retries of the decorator

        """
        logger = logging.getLogger(__name__)

        if not payload:
            return {"message": "FS: Stockpile is Empty"}

        if not api_key:
            return {"message": "FS: API key not set"}

        if not self.__url:
            logger.info("Backend URL is not set")
            return {"message": "FS: URL is not set"}

        headers = {"X-API-TOKEN": api_key}
        return_data: dict[str, str] = {}
        try:
            async with AsyncClient(headers=headers) as client:
                response = await client.post(url=self.__url, json=payload)
                try:
                    res_data = response.json()
                    # If the response is an error, return the error message, else return the
                    # response in message or the json response
                    return_data = res_data.get("error", res_data.get("message", res_data))
                except Exception:
                    logger.warning(
                        "FS: Error sending stockpile to the backend server. Status code: %d",
                        response.status_code,
                    )
                    return_data = {
                        "message": (
                            f"HTTP code {response.status_code} sending the information to "
                            "the backend server"
                        )
                    }
        except ConnectTimeout:
            raise
        except Exception as e:
            message = (
                f"FS: Error sending stockpile to the backend server: ({type(e).__name__}, {str(e)})"
            )
            logger.error(message)
            return_data = {"message": message}

        return return_data
