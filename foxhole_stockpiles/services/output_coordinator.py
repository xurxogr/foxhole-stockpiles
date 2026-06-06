"""Output coordinator for managing multiple output handlers."""

import logging
from typing import Any

from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    FileHandlerSettings,
    OutputHandlerConfig,
    OutputSettings,
    ReturnHandlerSettings,
    SheetsHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.console import ConsoleOutputHandler
from foxhole_stockpiles.handlers.file import FileOutputHandler
from foxhole_stockpiles.handlers.response import ReturnOutputHandler
from foxhole_stockpiles.handlers.sheets import SheetsOutputHandler
from foxhole_stockpiles.handlers.webhook import WebhookOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile


class OutputCoordinator:
    """Coordinates output handling by delegating to multiple configured handlers."""

    def __init__(self, output_settings: OutputSettings) -> None:
        """Initialize output coordinator with output settings.

        Args:
            output_settings (OutputSettings): Output settings containing handler configurations
        """
        self.output_settings = output_settings
        self.logger = logging.getLogger(__name__)

    def _create_handler(self, handler_config: OutputHandlerConfig) -> BaseOutputDestinationHandler:
        """Create a handler instance from configuration.

        Args:
            handler_config (OutputHandlerConfig): Handler configuration

        Returns:
            BaseOutputDestinationHandler: Handler instance

        Raises:
            ValueError: If handler type is not supported
        """
        handler_settings = handler_config.handler

        match handler_settings:
            case ReturnHandlerSettings():
                return ReturnOutputHandler()
            case FileHandlerSettings():
                return FileOutputHandler(
                    default_file_path=handler_settings.path,
                    format_settings=handler_config.format,
                )
            case WebhookHandlerSettings():
                return WebhookOutputHandler(webhook_settings=handler_settings)
            case ConsoleHandlerSettings():
                return ConsoleOutputHandler()
            case SheetsHandlerSettings():
                return SheetsOutputHandler(sheets_settings=handler_settings)
            case _:
                raise ValueError(f"Unsupported handler type: {type(handler_settings)}")

    async def handle_output(
        self,
        stockpiles: list[Stockpile],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Handle output to all configured handlers.

        Processes all configured handlers in order. The first handler that returns
        a non-None result will have its response passed back to the client.
        Handlers are processed in configuration order, so place the handler whose
        response should be returned first in the list.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to output
            **kwargs: Additional handler-specific parameters (e.g., token for webhooks)

        Returns:
            dict[str, Any] | None: Response data from the first handler that returns
                data, or None if no handler returns data
        """
        result: dict[str, Any] | None = None
        handlers = self.output_settings.handlers

        if not handlers:
            self.logger.warning("No output handlers configured")
            return None

        for handler_config in handlers:
            handler = self._create_handler(handler_config)
            handler_type = handler_config.handler.type

            self.logger.debug(
                "Processing handler '%s' (type: %s)",
                handler_config.name,
                handler_type,
            )

            try:
                handler_result = await handler.handle(stockpiles=stockpiles, **kwargs)

                # First handler that returns data becomes the API response
                if handler_result is not None and result is None:
                    result = handler_result
                    self.logger.debug(
                        "Handler '%s' response will be returned to client",
                        handler_config.name,
                    )

            except Exception as e:
                self.logger.error(
                    "Handler '%s' failed: %s",
                    handler_config.name,
                    str(e),
                )
                # Continue processing other handlers even if one fails

        return result
