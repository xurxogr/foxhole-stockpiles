import json
import logging
from logging.handlers import TimedRotatingFileHandler

from foxhole_stockpiles.core.config import settings
import os


class Logging():
    @staticmethod
    def configure_logging():
        """
        Initialize logging
        """

        logging.basicConfig(level=settings.logging.level, format=settings.logging.format, datefmt=settings.logging.date_format)

        loggers = {}
        try:
            loggers_options = settings.logging.loggers
            if loggers_options:
                loggers = json.loads(loggers_options)
        except:
            pass

        for logger, name_level in loggers.items():
            try:
                mappings = logging.getLevelNamesMapping()
                log_level = mappings.get(name_level.upper(), logging.WARNING)
                logging.getLogger(logger).setLevel(level=log_level)
            except:
                pass

        if settings.logging.file:
            log_folder = 'logs'
            if not os.path.exists(log_folder):
                os.makedirs(log_folder)
            
            file_handler = TimedRotatingFileHandler(filename=os.path.join(log_folder, 'foxhole_stockpiles.log'), when='midnight')
            file_handler.setFormatter(logging.Formatter(fmt=settings.logging.format, datefmt=settings.logging.date_format))
            logging.getLogger().addHandler(file_handler)
