"""Tests for the factory order models and their link to Stockpile."""

from typing import Any

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.factory_order import FactoryOrder
from foxhole_stockpiles.models.factory_order_item import FactoryOrderItem
from foxhole_stockpiles.models.stockpile import Stockpile

ORDER_DATA: dict[str, Any] = {
    "queue": 0,
    "queue_type": "SmallArms",
    "duration": 0,
    "items": [{"slot": 16, "code": "RifleC"}],
}


class TestFactoryOrderItem:
    """Test suite for FactoryOrderItem."""

    def test_code_optional(self) -> None:
        """An item without code is valid."""
        assert FactoryOrderItem(slot=255).code is None

    @pytest.mark.parametrize("slot", [-1, 256])
    def test_slot_out_of_range_rejected(self, slot: int) -> None:
        """A slot outside 0-255 is rejected."""
        with pytest.raises(ValidationError):
            FactoryOrderItem(slot=slot)


class TestFactoryOrder:
    """Test suite for FactoryOrder."""

    def test_round_trip(self) -> None:
        """The fs-sav payload round-trips through the model."""
        order = FactoryOrder.model_validate(ORDER_DATA)
        assert order.model_dump(exclude_none=True) == ORDER_DATA

    def test_optional_fields(self) -> None:
        """queue_type and items may be missing."""
        order = FactoryOrder(queue=3, duration=10)
        assert order.queue_type is None
        assert order.items == []

    def test_unknown_queue_type_accepted(self) -> None:
        """A queue name not known today is kept verbatim."""
        assert FactoryOrder(queue=0, queue_type="Naval", duration=0).queue_type == "Naval"

    def test_upper_limits_accepted(self) -> None:
        """The game limits are accepted."""
        order = FactoryOrder(queue=255, duration=64800)
        assert order.duration == 64800

    @pytest.mark.parametrize(
        ("field", "value"),
        [("queue", 256), ("queue", -1), ("duration", 64801), ("duration", -1)],
    )
    def test_out_of_range_rejected(self, field: str, value: int) -> None:
        """Values outside the game limits are rejected."""
        with pytest.raises(ValidationError):
            FactoryOrder.model_validate({**ORDER_DATA, field: value})

    def test_item_slot_out_of_range_rejected(self) -> None:
        """An item slot above 255 is rejected inside an order."""
        with pytest.raises(ValidationError):
            FactoryOrder.model_validate({**ORDER_DATA, "items": [{"slot": 256}]})


class TestStockpileTypeHasFactoryOrders:
    """Test suite for StockpileType.has_factory_orders."""

    @pytest.mark.parametrize(
        "value", [StockpileType.FACTORY, StockpileType.MASS_PRODUCTION_FACTORY]
    )
    def test_factories(self, value: str) -> None:
        """Factory and Mass Production Factory take orders."""
        assert StockpileType.has_factory_orders(value)

    @pytest.mark.parametrize("value", [StockpileType.SEAPORT, StockpileType.REFINERY, "New"])
    def test_others(self, value: str) -> None:
        """Other and unknown types do not."""
        assert not StockpileType.has_factory_orders(value)


class TestStockpileFactoryOrders:
    """Test suite for the factory_orders field on Stockpile."""

    @pytest.mark.parametrize(
        "stockpile_type", [StockpileType.FACTORY, StockpileType.MASS_PRODUCTION_FACTORY]
    )
    def test_orders_on_factory(self, stockpile_type: StockpileType) -> None:
        """A main factory stockpile accepts factory orders."""
        stockpile = Stockpile(
            type=stockpile_type, factory_orders=[FactoryOrder.model_validate(ORDER_DATA)]
        )
        assert stockpile.factory_orders is not None
        assert stockpile.factory_orders[0].items[0].code == "RifleC"

    def test_factory_without_orders_valid(self) -> None:
        """A factory does not require factory orders."""
        assert Stockpile(type=StockpileType.FACTORY).factory_orders is None

    def test_orders_on_seaport_rejected(self) -> None:
        """Factory orders on another stockpile type are rejected."""
        with pytest.raises(ValidationError, match="factory_orders is not allowed on 'Seaport'"):
            Stockpile(type=StockpileType.SEAPORT, factory_orders=[])

    def test_orders_on_reserve_rejected(self) -> None:
        """Factory orders on a reserve stockpile are rejected."""
        with pytest.raises(ValidationError, match="not allowed on reserve"):
            Stockpile(type=StockpileType.FACTORY, is_reserve=True, factory_orders=[])
