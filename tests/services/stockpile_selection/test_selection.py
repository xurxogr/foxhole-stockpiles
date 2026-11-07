"""Preparing the stockpiles of a send for one output."""

from foxhole_stockpiles.core.settings.sections.output import (
    FileHandlerSettings,
    ImageHandlerSettings,
    OutputHandlerConfig,
)
from foxhole_stockpiles.enums.public_stockpile_filter import PublicStockpileFilter
from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_selection.selection import select_for_output

_PUBLIC = Stockpile(name="Public", type=StockpileType.SEAPORT, hex="WestgateHex")
_RESERVE_A = Stockpile(name="A", type=StockpileType.SEAPORT, hex="WestgateHex", is_reserve=True)
_RESERVE_B = Stockpile(name="B", type=StockpileType.SEAPORT, hex="WestgateHex", is_reserve=True)


def test_public_stockpiles_are_left_out_before_grouping() -> None:
    """The merge does not add up what the output does not want."""
    config = OutputHandlerConfig(
        name="out",
        public_stockpiles=PublicStockpileFilter.NON_RESERVABLE,
        grouping=StockpileGrouping.ALL,
    )

    (group,) = select_for_output(
        handler_config=config, stockpiles=[_PUBLIC, _RESERVE_A, _RESERVE_B]
    )

    assert group.sources == [_RESERVE_A, _RESERVE_B]


def test_an_image_output_names_its_merges_in_its_language() -> None:
    """As the rest of the text of its images."""
    config = OutputHandlerConfig(
        name="out",
        handler=ImageHandlerSettings(language="es"),
        grouping=StockpileGrouping.ALL,
    )

    (group,) = select_for_output(handler_config=config, stockpiles=[_RESERVE_A, _RESERVE_B])

    assert group.drawn.name == "Todos los stockpiles"


def test_an_output_of_data_names_its_merges_in_english() -> None:
    """It has no language of its own."""
    config = OutputHandlerConfig(
        name="out",
        handler=FileHandlerSettings(path="out.json"),
        grouping=StockpileGrouping.ALL,
    )

    (group,) = select_for_output(handler_config=config, stockpiles=[_RESERVE_A, _RESERVE_B])

    assert group.drawn.name == "All Stockpiles"
