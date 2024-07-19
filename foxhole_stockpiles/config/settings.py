from configparser import ConfigParser
import json
import logging
import os
from typing import Final

from foxhole_stockpiles.config.env_interpolation import EnvInterpolation
from foxhole_stockpiles.models.singleton.singletonmeta import SingletonMeta


class Settings(metaclass=SingletonMeta):
    SECTION_OCR: Final = 'OCR'
    SECTION_LOGGING: Final = 'LOGGING'
    SECTION_MODELS: Final = 'MODELS'
    SECTION_DEVELOPER: Final = 'DEVELOPER'
    SECTION_HERMES: Final = 'HERMES'

    # OCR Options
    OPTION_OCR_ITEM_MIN_WIDTH: Final = 'item_min_w'
    OPTION_OCR_ITEM_MAX_WIDTH: Final = 'item_max_w'
    OPTION_OCR_ITEM_MIN_WH_RATIO: Final = 'item_min_ratio'
    OPTION_OCR_ITEM_MAX_WH_RATIO: Final = 'item_max_ratio'
    OPTION_OCR_ITEM_SPACING_HEIGHT: Final = 'item_spacing_height'
    OPTION_OCR_ITEM_SPACING_WIDTH: Final = 'item_spacing_width'

    # Logging options
    OPTION_LOG_LEVEL: Final = 'log_level'
    OPTION_LOGGERS: Final = 'loggers'

    # General options
    OPTION_ICONS_PATH: Final = 'icons_path'
    OPTION_QUANTITIES_PATH: Final = 'quantities_path'
    OPTION_CATALOG_ITEMS_PATH: Final = 'catalog_items_path'
    OPTION_BACKUP_PATH: Final = 'backup_path'

    # Developer options
    OPTION_DEV_DETECT_QUANTITIES: Final = 'detect_quantities'
    OPTION_DEV_DETECT_ICONS: Final = 'detect_icons'
    OPTION_DEV_DETECT_STOCKPILE_NAME: Final = 'detect_stockpile_name'
    OPTION_DEV_DETECT_STOCKPILE_TYPE: Final = 'detect_stockpile_type'
    OPTION_DEV_DRAW_RECTANGLES: Final = 'draw_rectangles'
    OPTION_DEV_SAVE_IMAGES: Final = 'save_images'

    # Hermes Options
    OPTION_URL: Final = 'url'


    def __init__(self) -> None:
        self.__config_parser = None

        filepath = os.path.dirname(os.path.realpath(__file__))
        self.__config_parser = ConfigParser(interpolation=EnvInterpolation())
        self.__config_parser.read(["{}/config.ini".format(filepath)])

        self.__check_section(section=self.SECTION_DEVELOPER, options=[
            self.OPTION_DEV_DETECT_ICONS, self.OPTION_DEV_DETECT_QUANTITIES, self.OPTION_DEV_DETECT_STOCKPILE_NAME,
            self.OPTION_DEV_DETECT_STOCKPILE_TYPE, self.OPTION_DEV_DRAW_RECTANGLES, self.OPTION_DEV_SAVE_IMAGES, self.OPTION_BACKUP_PATH])
        self.__check_section(section=self.SECTION_HERMES, options=[self.OPTION_URL])
        self.__check_section(section=self.SECTION_LOGGING, options=[self.OPTION_LOG_LEVEL, self.OPTION_LOGGERS])
        self.__check_section(section=self.SECTION_MODELS, options=[self.OPTION_ICONS_PATH, self.OPTION_QUANTITIES_PATH, self.OPTION_CATALOG_ITEMS_PATH])
        self.__check_section(section=self.SECTION_OCR, options=[
            self.OPTION_OCR_ITEM_MIN_WIDTH, self.OPTION_OCR_ITEM_MAX_WIDTH, self.OPTION_OCR_ITEM_MIN_WH_RATIO,
            self.OPTION_OCR_ITEM_MAX_WH_RATIO, self.OPTION_OCR_ITEM_SPACING_HEIGHT, self.OPTION_OCR_ITEM_SPACING_WIDTH])

        self.__init_logging()

    def __check_section(self, section: str, options: list[str]):
        """Checks for needed options in a section"""
        if not self.__config_parser.has_section(section):
            self.__config_parser.add_section(section)

        for option in options:
            if not self.__config_parser.has_option(section, option):
                self.__config_parser.set(section=section, option=option, value='')

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

    def get_section(self, section: str) -> dict:
        """
        gets a section from the config
        :param section: str = Name of the section
        :returns dict: Section as dictionary
        """

        return self.get_sections([ section ])

    def get_sections(self, sections: list) -> dict:
        """
        gets multiple sections from the config. If the same option exists in multiple sections it will be overwritten
        :param sections: list = List of sections to read
        :returns dict: Sections as dictionary
        """
        options = {}
        for section in sections:
            if self.__config_parser.has_section(section):
                options.update(dict(self.__config_parser[section]))

        return options

    def get(self, section: str, option: str) -> str:
        """
        gets an option from a section
        :param section: str = Section to read from
        :param option: str = Option to read from
        :returns str: Returns the value read
        """
        return self.__config_parser.get(section, option)

    def get_config(self) -> dict:
        """
        gets the whole config as a dict
        :returns dict: ConfigParser as dict
        """
        return self.get_sections(self.__config_parser.sections())
