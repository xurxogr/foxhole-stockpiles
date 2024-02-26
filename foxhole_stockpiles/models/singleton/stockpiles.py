from asyncio import create_task
import json
import logging

from pydantic import TypeAdapter

from foxhole_stockpiles.models.singleton.singletonmeta import SingletonMeta
from foxhole_stockpiles.models.stockpile import Stockpile


class Stockpiles(metaclass=SingletonMeta):
    STOCKPILE_FILE = 'data/stockpiles.json'
    def __init__(self):
        self.__stockpiles = {}
        self.__logger = logging.getLogger(__name__)
        create_task(self.async_init())

    async def async_init(self):
        """
        Async initialization
        """
        await self.load_data()

    async def load_data(self):
        """
        Loads the data (Stockpiles)
        """
        try:
            with open(Stockpiles.STOCKPILE_FILE, encoding='utf-8') as file:
                data = json.load(file)
        except Exception:
            data = {}

        for key, value in data.items():
            try:
                if key == 'stockpiles':
                    stockpiles = TypeAdapter(list[Stockpile]).validate_python(value)
                    self.__stockpiles = { stockpile.uid: stockpile for stockpile in stockpiles }
            except Exception as ex:
                self.__logger.warning("Error loading the stockpiles. {}".format(str(ex)))

    async def save_data(self):
        """
        Saves the data
        """
        self.__logger.info("Saving stockpiles: {}".format(len(self.__stockpiles)))
        try:
            data = {
                "stockpiles": [x.model_dump(exclude_none=True) for x in self.__stockpiles.values()]
            }

            with open(Stockpiles.STOCKPILE_FILE, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

        except Exception as ex:
            self.__logger.warning("Error saving the stockpiles. {}".format(str(ex)))

    async def get_stockpiles(self) -> list[Stockpile]:
        """
        Gets the list of stockpiles
        """
        return [ x for x in self.__stockpiles.values()]

    async def add_stockpile(self, stockpile: Stockpile) -> str:
        """
        Adds a new stockpile
        :param stockpile: Stockpile = The stockpile to add
        :returns str: Error add or None if added properly
        """

        if await self.get_stockpile(name=stockpile.name, region=stockpile.region):
            message = "name: '{}' and region: {}'. Stockpile already exists".format(stockpile.name, stockpile.region)
            self.__logger.debug("name: '{}' and region: {}'. Stockpile already exists".format(stockpile.name, stockpile.region))
            return message

        self.__stockpiles[stockpile.uid] = stockpile
        self.__logger.info("name: '{}' and region: {}'. Stockpile added with uid: '{}'".format(stockpile.name, stockpile.region, stockpile.uid))

        await self.save_data()

    async def get_stockpile(self, *, uid: str = None, name: str = None, region: str = None) -> Stockpile:
        """
        Finds an stockpile by uid or by name and region
        :param uid: str = uid.
        :param name: str = Name of the stockpile
        :param region: str = Region of the stockpile
        :returns Stockpile: Stockpile found or None
        """

        if uid:
            return self.__stockpiles.get(uid)

        if name and region:
            stockpile: Stockpile
            for stockpile in self.__stockpiles.values():
                if stockpile.name == name and stockpile.region == region:
                    return stockpile

        return None

    async def del_stockpile(self, *, uid: str = None, name: str = None, region: str = None) -> bool:
        """
        Deletes an stockpile by uid or by name and region
        :param uid: str = uid.
        :param name: str = Name of the stockpile
        :param region: str = Region of the stockpile
        :returns bool: Deleted?
        """
        if uid:
            if uid in self.__stockpiles:
                del self.__stockpiles[uid]
                await self.save_data()
                return True

            return False

        stockpile: Stockpile
        stockpile = await self.get_stockpile(name=name, region=region)
        if stockpile:
            del self.__stockpiles[stockpile.uid]
            await self.save_data()
            return True

        return False

    async def modify_stockpile(self, stockpile: Stockpile, **kwargs) -> str|bool:
        """
        Modifies an existing stockpile by uid or by name and region
        :param uid: str = Uid of the stockpile
        :param name: str = Name of the stockpile
        :param region: str = Region of the stockpile
        :param stockpile: Stockpile = Stockpile to modify
        :returns str|bool: False it not found, True if modified. str if error
        """

        sp: Stockpile
        sp = await self.get_stockpile(**kwargs)
        if not sp:
            return "Stockpile not found"

        if stockpile.uid:
            if stockpile.uid != sp.uid:
                return "Can't change the stockpile uid"
        else:
            stockpile.uid = sp.uid

        if stockpile.name:
            if stockpile.name != sp.name:
                return "Can't change the stockpile name"
        else:
            stockpile.name = sp.name

        if stockpile.region:
            if stockpile.region != sp.region:
                return "Can't change the stockpile region"
        else:
            stockpile.region = sp.region

        self.__stockpiles[stockpile.uid] = stockpile
        await self.save_data()
