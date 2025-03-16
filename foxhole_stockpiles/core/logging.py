"""Logging Module."""

import logging
import os
from logging.handlers import TimedRotatingFileHandler


class Logging:
    """Logging class."""

    def __init__(self, level: str, log_format: str, date_format: str, loggers: dict) -> None:
        """Initialize the Logging class.

        Args:
            level (str): Logging level
            log_format (str): Logging format
            date_format (str): Date format
            loggers (dict): Loggers to configure
        """
        self.level = level
        self.log_format = log_format
        self.date_format = date_format
        self.loggers = loggers

    async def configure_logging(self) -> None:
        """Initialize logging."""
        logging.basicConfig(level=self.level, format=self.log_format, datefmt=self.date_format)

        if self.loggers:
            for logger, name_level in self.loggers.items():
                mappings = logging.getLevelNamesMapping()
                log_level = mappings.get(name_level.upper(), logging.WARNING)
                logging.getLogger(logger).setLevel(level=log_level)

        log_folder = "logs"
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_folder, "foxhole_stockpiles.log"),
            when="midnight",
        )
        file_handler.setFormatter(logging.Formatter(fmt=self.log_format, datefmt=self.date_format))
        logging.getLogger().addHandler(file_handler)
