from configparser import ConfigParser
from configparser import NoSectionError
from configparser import NoOptionError
import json
import logging
import os

from foxhole_stockpiles.config.env_interpolation import EnvInterpolation
from foxhole_stockpiles.models.singleton.singletonmeta import SingletonMeta


class Settings(metaclass=SingletonMeta):
    SECTION_OCR = 'OCR'
    SECTION_LOGGING = 'LOGGING'
    SECTION_DISCORD_BOT = 'DISCORD_BOT'
    SECTION_GENERAL = 'GENERAL'

    # OCR Options
    OPTION_OCR_ITEM_MIN_WIDTH = 'item_min_w'
    OPTION_OCR_ITEM_MAX_WIDTH = 'item_max_w'
    OPTION_OCR_ITEM_MIN_WH_RATIO = 'item_min_ratio'
    OPTION_OCR_ITEM_MAX_WH_RATIO = 'item_max_ratio'
    OPTION_OCR_ITEM_SPACING_HEIGHT = 'item_spacing_height'
    OPTION_OCR_ITEM_SPACING_WIDTH = 'item_spacing_width'

    # Logging options
    OPTION_LOG_LEVEL = 'log_level'
    OPTION_LOGGERS = 'loggers'

    # Discord Bot options
    OPTION_DISCORD_BOT_URL = 'url'
    OPTION_DISCORD_BOT_SECRET = 'secret'
    OPTION_DISCORD_BOT_GUILDID = 'guildid'

    # General options
    OPTION_DEBUG = 'debug'
    OPTION_ICONS_PATH = 'icons_path'

    def __init__(self) -> None:
        self.__logger = logging.getLogger(__name__)
        self.__config_parser = None

        filepath = os.path.dirname(os.path.realpath(__file__))
        self.__config_parser = ConfigParser(interpolation=EnvInterpolation())
        self.__config_parser.read(["{}/config.ini".format(filepath)])

        self.__check_section_logging()
        self.__check_section_ocr()
        self.__check_section_discord_bot()
        self.__check_section_general()

    def get_section(self, section: str) -> dict:
        return self.get_sections([ section ])

    def get_sections(self, sections: list) -> dict:
        options = {}
        for section in sections:
            if self.__config_parser.has_section(section):
                options.update(dict(self.__config_parser[section]))

        return options

    def get(self, section: str, option: str) -> any:
        return self.__config_parser.get(section, option)

    def get_config(self) -> dict:
        return self.get_sections(self.__config_parser.sections())

    def __check_section_ocr(self):
        """Checks for needed options in OCR section"""
        section = self.SECTION_OCR
        if not self.__config_parser.has_section(section):
            raise NoSectionError(section)

        for option in [self.OPTION_OCR_ITEM_MIN_WIDTH, self.OPTION_OCR_ITEM_MAX_WIDTH, self.OPTION_OCR_ITEM_MIN_WH_RATIO,
                       self.OPTION_OCR_ITEM_MAX_WH_RATIO, self.OPTION_OCR_ITEM_SPACING_HEIGHT, self.OPTION_OCR_ITEM_SPACING_WIDTH]:
            if not self.__config_parser.has_option(section, option):
                 raise NoOptionError(option, section)

    def __check_section_logging(self):
        """Checks for needed options in logging section (optional)"""
        log_level = 'INFO'
        section = self.SECTION_LOGGING
        if self.__config_parser.has_section(section):
            log_level = self.__config_parser.get(section, self.OPTION_LOG_LEVEL) or 'INFO'

        logging.basicConfig(level=log_level)
        loggers = json.loads(self.__config_parser.get(section, self.OPTION_LOGGERS) or {})
        for logger, name_level in  loggers.items():
            try:
                log_level = logging._nameToLevel.get(name_level, logging.WARNING)
                logging.getLogger(logger).setLevel(level=log_level)
            except:
                pass

    def __check_section_discord_bot(self):
        """Checks for needed options in DISCORD_BOT section (optional)"""
        section = self.SECTION_DISCORD_BOT

        # Section is optional
        if not self.__config_parser.has_section(section):
            return

        # Check if all the options are empty or all of them have values.
        value_options = []
        options = [self.OPTION_DISCORD_BOT_URL, self.OPTION_DISCORD_BOT_SECRET, self.OPTION_DISCORD_BOT_GUILDID]
        for option in options:
            value_options.append(self.__config_parser.has_option(section, option))

        # If any of them have a value but not the others, log error and clean the options
        if any(value_options) and not all(value_options):
            self.__logger.info('Deleting discord Bot options as not all options where configured (url, secret, guildid)')
            for option in options:
                self.__config_parser.set(section, option, None)

    def __check_section_general(self):
        section = self.SECTION_GENERAL
        if not self.__config_parser.has_section(section):
            raise NoSectionError(section)

        for option in [self.OPTION_DEBUG, self.OPTION_ICONS_PATH]:
            if not self.__config_parser.has_option(section, option):
                 raise NoOptionError(option, section)
