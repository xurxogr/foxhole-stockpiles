"""Prepare the stockpiles of a send for one output."""

from foxhole_stockpiles.core.settings.sections.output.handler_config import OutputHandlerConfig
from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_group import StockpileGroup
from foxhole_stockpiles.services.catalog_service import get_catalog_service
from foxhole_stockpiles.services.stockpile_image.image_text import DEFAULT_LANGUAGE, ImageText
from foxhole_stockpiles.services.stockpile_selection.grouping import group_stockpiles
from foxhole_stockpiles.services.stockpile_selection.public_filter import filter_public


def _language_of(handler_config: OutputHandlerConfig) -> str:
    """Tell in which language an output names its merges.

    Args:
        handler_config (OutputHandlerConfig): The output.

    Returns:
        str: The language of its images, or English for the outputs of data.
    """
    handler = handler_config.handler
    return handler.language if isinstance(handler, StockpileImageSettings) else DEFAULT_LANGUAGE


def select_for_output(
    handler_config: OutputHandlerConfig, stockpiles: list[Stockpile]
) -> list[StockpileGroup]:
    """Filter and group the stockpiles of a send as an output asks.

    Args:
        handler_config (OutputHandlerConfig): The output.
        stockpiles (list[Stockpile]): The stockpiles of the send.

    Returns:
        list[StockpileGroup]: What the output receives, each with the stockpiles of
            the send it stands for.
    """
    wanted = filter_public(
        stockpiles=stockpiles, public_stockpiles=handler_config.public_stockpiles
    )
    return group_stockpiles(
        stockpiles=wanted,
        grouping=handler_config.grouping,
        group_name=handler_config.group_name,
        labels=ImageText(catalog=get_catalog_service(), language=_language_of(handler_config)),
    )
