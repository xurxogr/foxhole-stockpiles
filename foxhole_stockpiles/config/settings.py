from configparser import ConfigParser
import json
import logging
from typing import Final

from foxhole_stockpiles.config.env_interpolation import EnvInterpolation
from foxhole_stockpiles.models.singleton.singletonmeta import SingletonMeta


class Settings(metaclass=SingletonMeta):
    __FILE_NAME: Final = 'options.ini'
    __USER_FILE_NAME: Final = 'user.ini'

    SECTION_OCR: Final = 'OCR'
    SECTION_LOGGING: Final = 'LOGGING'
    SECTION_MODELS: Final = 'MODELS'
    SECTION_DEVELOPER: Final = 'DEVELOPER'

    # OCR Options
    OPTION_OCR_ITEM_MIN_WIDTH: Final = 'item_min_w'
    OPTION_OCR_ITEM_MAX_WIDTH: Final = 'item_max_w'
    OPTION_OCR_ITEM_MIN_WH_RATIO: Final = 'item_min_ratio'
    OPTION_OCR_ITEM_MAX_WH_RATIO: Final = 'item_max_ratio'
    OPTION_OCR_ITEM_SPACING_HEIGHT: Final = 'item_spacing_height'
    OPTION_OCR_ITEM_SPACING_WIDTH: Final = 'item_spacing_width'
    OPTION_OCR_STOCKPILE_MIN_WIDTH: Final = 'stockpile_min_width'

    # Logging options
    OPTION_LOG_LEVEL: Final = 'log_level'
    OPTION_LOGGERS: Final = 'loggers'

    # General options
    OPTION_ICONS_PATH: Final = 'icons_path'
    OPTION_QUANTITIES_PATH: Final = 'quantities_path'
    OPTION_CATALOG_ITEMS_PATH: Final = 'catalog_items_path'

    # Developer options
    OPTION_DEV_DETECT_QUANTITIES: Final = 'detect_quantities'
    OPTION_DEV_DETECT_ICONS: Final = 'detect_icons'
    OPTION_DEV_DETECT_STOCKPILE_NAME: Final = 'detect_stockpile_name'
    OPTION_DEV_DETECT_STOCKPILE_TYPE: Final = 'detect_stockpile_type'
    OPTION_DEV_DRAW_RECTANGLES: Final = 'draw_rectangles'

    # User options
    SECTION_KEYBIND: Final = 'KEYBIND'
    SECTION_SERVER: Final = 'SERVER'
    # Keybind options
    OPTION_KEY = 'KEY'
    # Server options
    OPTION_URL = 'URL'
    OPTION_TOKEN = 'TOKEN'

    def __init__(self) -> None:
        self.__config_parser = ConfigParser(interpolation=EnvInterpolation())
        self.__user_config_parser = ConfigParser(interpolation=EnvInterpolation())
        self.__config_parser.read(self.__FILE_NAME)
        self.__user_config_parser.read(self.__USER_FILE_NAME)

        self.__check_section(section=self.SECTION_DEVELOPER, options=[
            self.OPTION_DEV_DETECT_ICONS, self.OPTION_DEV_DETECT_QUANTITIES, self.OPTION_DEV_DETECT_STOCKPILE_NAME,
            self.OPTION_DEV_DETECT_STOCKPILE_TYPE, self.OPTION_DEV_DRAW_RECTANGLES])
        self.__check_section(section=self.SECTION_LOGGING, options=[self.OPTION_LOG_LEVEL, self.OPTION_LOGGERS])
        self.__check_section(section=self.SECTION_MODELS, options=[self.OPTION_ICONS_PATH, self.OPTION_QUANTITIES_PATH, self.OPTION_CATALOG_ITEMS_PATH])
        self.__check_section(section=self.SECTION_OCR, options=[
            self.OPTION_OCR_ITEM_MIN_WIDTH, self.OPTION_OCR_ITEM_MAX_WIDTH, self.OPTION_OCR_ITEM_MIN_WH_RATIO,
            self.OPTION_OCR_ITEM_MAX_WH_RATIO, self.OPTION_OCR_ITEM_SPACING_HEIGHT, self.OPTION_OCR_ITEM_SPACING_WIDTH,
            self.OPTION_OCR_STOCKPILE_MIN_WIDTH])

        self.__check_section(section=self.SECTION_KEYBIND, options=[self.OPTION_KEY], user=True)
        self.__check_section(section=self.SECTION_SERVER, options=[self.OPTION_URL, self.OPTION_TOKEN], user=True)

        self.__init_logging()

    def __check_section(self, section: str, options: list[str], user: bool = False):
        """Checks for needed options in a section"""
        config_parser = self.__user_config_parser if user else self.__config_parser
        if not config_parser.has_section(section):
            config_parser.add_section(section)

        for option in options:
            if not config_parser.has_option(section, option):
                config_parser.set(section=section, option=option, value='')

    def __init_logging(self):
        """Checks for needed options in logging section (optional)"""
        log_level = 'INFO'
        section = self.SECTION_LOGGING
        if self.__config_parser.has_section(section):
            log_level = self.__config_parser.get(section, self.OPTION_LOG_LEVEL) or 'INFO'

        logging.basicConfig(level=log_level)
        loggers = json.loads(self.__config_parser.get(section, self.OPTION_LOGGERS) or '{}')
        for logger, name_level in loggers.items():
            try:
                log_level = logging._nameToLevel.get(name_level, logging.WARNING)
                logging.getLogger(logger).setLevel(level=log_level)
            except:
                pass

    def __select_config_parser(self, section: str):
        """
        select the config parser depending on the section
        :param section: str = Section
        :returns config_parser:
        """
        if section in [self.SECTION_SERVER, self.SECTION_KEYBIND]:
            return self.__user_config_parser

        return self.__config_parser

    def get(self, section: str, option: str) -> str:
        """
        gets an option from a section
        :param section: str = Section to read from
        :param option: str = Option to read from
        :returns str: Returns the value read
        """
        config_parser = self.__select_config_parser(section=section)
        return config_parser.get(section, option)

    def set(self, section: str, option: str, value: any):
        """
        sets option for a section
        :param section: str = Section
        :param option: str = Option
        :param value: any = Value to set
        """
        config_parser = self.__select_config_parser(section=section)
        return config_parser.set(section=section, option=option, value=value)

    def save(self):
        """
        Saves the config to file
        """
        with open(self.__USER_FILE_NAME, 'w') as file:
            self.__user_config_parser.write(file)