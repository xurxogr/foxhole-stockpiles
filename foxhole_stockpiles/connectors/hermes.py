from httpx import AsyncClient

from foxhole_stockpiles.config.settings import Settings


class HermesConnector():
    def __init__(self, url: None):
        settings = Settings()
        if url is None:
            self.__url = settings.get(section=Settings.SECTION_HERMES, option=Settings.OPTION_URL)
        else:
            self.__url = url

    async def send_stockpile_to_hermes(self, stockpile: dict, api_key: str):
        """
        Sends an stockpile to hermes
        :param stockpile: Stockpile = Stockpile to send (Generated from an image)
        :param api_key: str = API_KEY header to use for authentication
        """
        if not stockpile:
            return { "message": "Stockpile is Empty" }

        if not api_key:
            return { "message": "API key not set" }
        
        if not self.__url:
            return { "message": "URL is not set" }

        headers = { "X-API-TOKEN": api_key }
        return_data = {}
        async with AsyncClient(verify=False, headers=headers) as client:
            response = await client.post(url=self.__url, json=stockpile)
            if response.status_code == 200:
                try:
                    return_data = response.json()
                except:
                    return_data = { "message": response.text }
            else:
                return_data = { "message": response.text }

        return return_data
