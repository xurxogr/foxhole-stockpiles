"""Output coordinator for managing multiple output handlers."""

import logging
from typing import Any

from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    DiscordHandlerSettings,
    FileHandlerSettings,
    ImageHandlerSettings,
    OutputHandlerConfig,
    OutputSettings,
    ReturnHandlerSettings,
    SheetsHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.console import ConsoleOutputHandler
from foxhole_stockpiles.handlers.discord import DiscordOutputHandler
from foxhole_stockpiles.handlers.file import FileOutputHandler
from foxhole_stockpiles.handlers.image import ImageOutputHandler
from foxhole_stockpiles.handlers.response import ReturnOutputHandler
from foxhole_stockpiles.handlers.sheets import SheetsOutputHandler
from foxhole_stockpiles.handlers.webhook import WebhookOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile

# The response surfaced by the first return/webhook handler: a dict (return /
# sheets), a list of messages (webhook), or None (console / file only).
OutputResponse = dict[str, Any] | list[str] | None


class OutputCoordinator:
    """Coordinates output handling by delegating to multiple configured handlers."""

    def __init__(self, output_settings: OutputSettings) -> None:
        """Initialize output coordinator with output settings.

        Args:
            output_settings (OutputSettings): Output settings containing handler configurations
        """
        self.output_settings = output_settings
        self.logger = logging.getLogger(__name__)
        # By handler position, then stockpile key: what that handler still has to receive.
        self._undelivered: dict[int, dict[str, Stockpile]] = {}

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
            case ImageHandlerSettings():
                return ImageOutputHandler(image_settings=handler_settings)
            case DiscordHandlerSettings():
                return DiscordOutputHandler(discord_settings=handler_settings)
            case _:
                raise ValueError(f"Unsupported handler type: {type(handler_settings)}")

    async def handle_output(
        self,
        stockpiles: list[Stockpile],
        **kwargs: Any,
    ) -> OutputResponse:
        """Handle output to all configured handlers.

        Processes all configured handlers in order. The first handler that returns
        a non-None result will have its response passed back to the client.
        Handlers are processed in configuration order, so place the handler whose
        response should be returned first in the list.

        A handler that fails receives that batch again with the next call, while the
        ones that delivered it do not, so a retry cannot duplicate rows in a sheet.

        Args:
            stockpiles (list[Stockpile]): The stockpile data to output
            **kwargs: Additional handler-specific parameters (e.g., token for webhooks)

        Returns:
            dict[str, Any] | list[str] | None: Response data from the first handler
                that returns data (a dict, a list of messages, or None)
        """
        result: dict[str, Any] | list[str] | None = None
        handlers = self.output_settings.handlers

        if not handlers:
            self.logger.warning("No output handlers configured")
            return None

        for position, handler_config in enumerate(handlers):
            batch = self._batch_for(position=position, stockpiles=stockpiles)
            handler_result, undelivered = await self._run_handler(
                handler_config=handler_config, batch=batch, **kwargs
            )
            # First handler that returns data becomes the result of the send
            if handler_result is not None and result is None:
                result = handler_result
                self.logger.debug(
                    "Handler '%s' response will be the result of the send",
                    handler_config.name,
                )
            self._track_delivery(
                position=position, name=handler_config.name, undelivered=undelivered
            )

        return result

    async def _run_handler(
        self, handler_config: OutputHandlerConfig, batch: list[Stockpile], **kwargs: Any
    ) -> tuple[OutputResponse, list[Stockpile]]:
        """Give a batch to one handler; its failure must not block the rest.

        Args:
            handler_config (OutputHandlerConfig): The configuration of the handler.
            batch (list[Stockpile]): The stockpiles to give it.
            **kwargs: Additional handler-specific parameters.

        Returns:
            tuple[OutputResponse, list[Stockpile]]: What the handler returned, and the
                stockpiles that did not reach the destination.
        """
        self.logger.debug(
            "Processing handler '%s' (type: %s)",
            handler_config.name,
            handler_config.handler.type,
        )
        result: OutputResponse = None
        undelivered = batch
        try:
            handler = self._create_handler(handler_config)
        except Exception as e:  # noqa: BLE001 - one handler's failure must not block the rest
            self.logger.error("Handler '%s' could not be created: %s", handler_config.name, e)
            return result, undelivered

        try:
            result = await handler.handle(stockpiles=batch, **kwargs)
            undelivered = handler.undelivered(batch)
        except Exception as e:  # noqa: BLE001 - one handler's failure must not block the rest
            self.logger.error("Handler '%s' failed: %s", handler_config.name, e)
        finally:
            await self._close_handler(handler=handler, name=handler_config.name)
        return result, undelivered

    def _batch_for(self, position: int, stockpiles: list[Stockpile]) -> list[Stockpile]:
        """Add what a handler still has to receive to a new batch.

        Args:
            position (int): The position of the handler in the configuration.
            stockpiles (list[Stockpile]): The new stockpiles.

        Returns:
            list[Stockpile]: The stockpiles to send, a newer version replacing an
                undelivered one of the same stockpile.
        """
        undelivered = self._undelivered.get(position)
        if not undelivered:
            return stockpiles
        merged = {**undelivered, **{stockpile.to_key(): stockpile for stockpile in stockpiles}}
        return list(merged.values())

    def _track_delivery(self, position: int, name: str, undelivered: list[Stockpile]) -> None:
        """Remember what a handler failed to deliver, or forget it once it has all arrived.

        Args:
            position (int): The position of the handler in the configuration.
            name (str): Its configured name, for the log.
            undelivered (list[Stockpile]): The stockpiles that did not reach the destination.
        """
        if not undelivered:
            self._undelivered.pop(position, None)
            return
        self._undelivered[position] = {stockpile.to_key(): stockpile for stockpile in undelivered}
        self.logger.warning(
            "Handler '%s' did not deliver %d stockpile(s); they go again with the next batch",
            name,
            len(undelivered),
        )

    async def _close_handler(self, handler: BaseOutputDestinationHandler, name: str) -> None:
        """Release a handler's resources without affecting the remaining handlers.

        Args:
            handler (BaseOutputDestinationHandler): The handler to close.
            name (str): Its configured name, for the log.
        """
        try:
            await handler.close()
        except Exception as e:  # noqa: BLE001 - a failed cleanup must not block the rest
            self.logger.warning("Handler '%s' failed to close: %s", name, e)
