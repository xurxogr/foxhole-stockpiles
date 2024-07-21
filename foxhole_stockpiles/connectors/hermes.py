from asyncio import sleep
import functools
import logging

from httpx import AsyncClient


from foxhole_stockpiles.config.settings import Settings

from httpx import ConnectTimeout

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


class HermesConnector():
    def __init__(self, url: None):
        settings = Settings()
        if url is None:
            self.__url = settings.get(section=Settings.SECTION_HERMES, option=Settings.OPTION_URL)
        else:
            self.__url = url

    @async_retry_on_connect_timeout(max_retries=3, delay=2)
    async def send_stockpile_to_hermes(self, stockpile: dict, api_key: str):
        """
        Sends an stockpile to hermes
        :param stockpile: Stockpile = Stockpile to send (Generated from an image)
        :param api_key: str = API_KEY header to use for authentication
        """
        if not stockpile:
            return { "message": "FS: Stockpile is Empty" }

        if not api_key:
            return { "message": "FS: API key not set" }

        if not self.__url:
            return { "message": "FS: URL is not set" }

        logger = logging.getLogger(__name__)
        headers = { "X-API-TOKEN": api_key }
        return_data = {}
        try:
            async with AsyncClient(verify=False, headers=headers) as client:
                response = await client.post(url=self.__url, json=stockpile)
                if response.status_code == 200:
                    try:
                        return_data = response.json()
                        # If the response is an error, return the error message, else return the response in message or the json response
                        return_data = return_data.get('error', return_data.get('message', return_data))
                    except:
                        logger.error("FS: Error parsing response from the backend server: {}".format(response.text))
                        return_data = { "message": "Error reading the response from the backend server" }
                else:
                    logger.warning("FS: Error sending stockpile to the backend server: {}: {}".format(response.status_code, response.text))
                    return_data = { "message": "HTTP code {} sending the information to the backend server".format(response.status_code) }
        except ConnectTimeout:
            raise
        except Exception as e:
            logger.error("FS: Error sending stockpile to the backend server: ({}: {})".format(type(e).__name__, str(e)))
            return_data = { "message": "FS: Error sending stockpile to the backend server: ({})".format(type(e).__name__) }

        return return_data
