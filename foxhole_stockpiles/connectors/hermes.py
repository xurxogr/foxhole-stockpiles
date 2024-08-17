from asyncio import sleep
import functools
import logging

from httpx import AsyncClient
from httpx import ConnectTimeout

from foxhole_stockpiles.core.config import settings


def async_retry_on_connect_timeout(max_retries=3, delay=1):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except ConnectTimeout as e:
                    retries += 1
                    if retries == max_retries:
                        raise e

                    logger = logging.getLogger(__name__)
                    logger.info("ConnectTimeout occurred. Retrying ({}/{})...".format(retries, max_retries))
                    await sleep(delay)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def async_retry_on_302(max_retries=3, delay=1):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                response = await func(*args, **kwargs)
                if response.status_code != 302:
                    return response

                logger = logging.getLogger(__name__)
                logger.info("302 occurred. Retrying ({}/{})...".format(retries, max_retries))
                await sleep(delay)
                retries += 1

            return await func(*args, **kwargs)
        return wrapper
    return decorator

class HermesConnector():
    def __init__(self, url: str = None):
        self.__url = url or settings.backend.url

    #@async_retry_on_302(max_retries=3, delay=2)
    @async_retry_on_connect_timeout(max_retries=3, delay=2)
    async def send_stockpile_to_hermes(self, stockpile: dict, api_key: str):
        """
        Sends an stockpile to hermes
        :param stockpile: Stockpile = Stockpile to send (Generated from an image)
        :param api_key: str = API_KEY header to use for authentication
        """
        logger = logging.getLogger(__name__)

        if not stockpile:
            return { "message": "FS: Stockpile is Empty" }

        if not api_key:
            return { "message": "FS: API key not set" }

        if not self.__url:
            logger.info("Backend URL is not set")
            return { "message": "FS: URL is not set" }

        headers = { "X-API-TOKEN": api_key }
        return_data = {}
        try:
            async with AsyncClient(verify=False, headers=headers) as client:
                response = await client.post(url=self.__url, json=stockpile)
                try:
                    return_data = response.json()
                    # If the response is an error, return the error message, else return the response in message or the json response
                    return_data = return_data.get('error', return_data.get('message', return_data))
                except:
                    logger.warning(f"FS: Error sending stockpile to the backend server. Status code: {response.status_code}")
                    return_data = { "message": f"HTTP code {response.status_code} sending the information to the backend server" }
        except ConnectTimeout:
            raise
        except Exception as e:
            message = f"FS: Error sending stockpile to the backend server: ({type(e).__name__}, {str(e)})"
            logger.error(message)
            return_data = { "message": message }

        return return_data
