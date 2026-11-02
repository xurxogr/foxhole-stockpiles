"""Logging configuration for Foxhole Stockpiles."""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Final, Protocol

# Handler names used to identify handlers and avoid duplicates
QT_GUI_HANDLER_NAME = "foxhole_qt_gui_handler"
APP_STREAM_HANDLER_NAME = "foxhole_app_stream_handler"
APP_FILE_HANDLER_NAME = "foxhole_app_file_handler"

# httpx logs every request URL at INFO, and a webhook URL can be a credential
# (Discord's holds its token), so it only logs problems unless configured otherwise.
_QUIET_LOGGERS: Final[dict[str, int]] = {"httpx": logging.WARNING}


class LoggingConfig(Protocol):
    """The logging options ``setup_logging`` reads."""

    loggers: dict[str, str]
    log_level: str
    log_format: str
    date_format: str
    rotate_logs: bool
    log_file: str | None


def _get_handler_by_name(logger: logging.Logger, name: str) -> logging.Handler | None:
    """Get a handler by name from a logger.

    Args:
        logger: Logger to search
        name: Handler name to find

    Returns:
        Handler if found, None otherwise
    """
    for handler in logger.handlers:
        if getattr(handler, "name", None) == name:
            return handler
    return None


def _remove_handler_by_name(logger: logging.Logger, name: str) -> None:
    """Remove a handler by name from a logger.

    Args:
        logger: Logger to remove from
        name: Handler name to remove
    """
    handler = _get_handler_by_name(logger, name)
    if handler:
        logger.removeHandler(handler)
        handler.close()


def _get_min_level(root_level: str, loggers: dict[str, str]) -> int:
    """Get the minimum log level from root and all custom loggers.

    Args:
        root_level: The root logger level string
        loggers: Dict of logger name to level string

    Returns:
        The minimum numeric log level
    """
    levels: list[int] = [logging.getLevelName(root_level.upper())]
    for level in loggers.values():
        levels.append(logging.getLevelName(level.upper()))
    return min(levels)


def setup_logging(settings: LoggingConfig) -> None:
    """Setup logging configuration for the application.

    Args:
        settings (LoggingConfig): Logging settings to configure logging.

    Note:
        This function manages handlers by name to avoid duplicates and preserve
        existing handlers (like the Qt GUI handler). It does NOT use force=True
        to avoid removing handlers added by other parts of the application.

        Handler level is set to the minimum of all configured levels so that
        child loggers with lower levels than root can still output messages.
    """
    root_logger = logging.getLogger()

    # Calculate minimum level across root and all custom loggers
    # This ensures handlers accept messages from loggers with lower levels than root
    min_level = _get_min_level(settings.log_level, settings.loggers)

    # Set the root logger level (controls default for loggers without explicit level)
    root_logger.setLevel(settings.log_level)

    # Remove any existing app handlers (we'll recreate them with new settings)
    _remove_handler_by_name(root_logger, APP_STREAM_HANDLER_NAME)
    _remove_handler_by_name(root_logger, APP_FILE_HANDLER_NAME)

    # Create formatter
    formatter = logging.Formatter(fmt=settings.log_format, datefmt=settings.date_format)

    # Create and add the appropriate handler
    if settings.log_file:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if settings.rotate_logs:
            handler: logging.Handler = TimedRotatingFileHandler(
                filename=log_path,
                when="midnight",
                encoding="utf-8",
            )
        else:
            handler = logging.FileHandler(log_path, encoding="utf-8")

        handler.set_name(APP_FILE_HANDLER_NAME)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name(APP_STREAM_HANDLER_NAME)

    handler.setFormatter(formatter)
    handler.setLevel(min_level)
    root_logger.addHandler(handler)

    # Update Qt GUI handler level if present
    qt_handler = _get_handler_by_name(root_logger, QT_GUI_HANDLER_NAME)
    if qt_handler:
        qt_handler.setLevel(min_level)

    for logger_name, quiet_level in _QUIET_LOGGERS.items():
        logging.getLogger(logger_name).setLevel(quiet_level)

    # Configure individual logger levels from settings
    for logger_name, level in settings.loggers.items():
        logging.getLogger(logger_name).setLevel(level)
