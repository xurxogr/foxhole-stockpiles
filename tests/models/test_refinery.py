"""Tests for the refinery models and their link to Stockpile."""

from typing import Any

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.enums.refinery_access_level import RefineryAccessLevel
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.refinery import Refinery
from foxhole_stockpiles.models.refinery_access import RefineryAccess
from foxhole_stockpiles.models.refinery_order import RefineryOrder
from foxhole_stockpiles.models.refinery_storage import RefineryStorage
from foxhole_stockpiles.models.stockpile import Stockpile

REFINERY_DATA: dict[str, Any] = {
    "orders_access": {"level": "public"},
    "orders": [{"slot": 0, "code": "Cloth", "source": 0, "refined": 50, "duration": 0}],
    "storages": [
        {
            "access": {"level": "squad", "squad_id": 1},
            "slot": 1,
            "code": "Diesel",
            "refined": 5309,
        }
    ],
}

ORDER_BASE: dict[str, Any] = {"slot": 0, "source": 0, "refined": 0, "duration": 0}


class TestRefineryAccess:
    """Test suite for RefineryAccess."""

    def test_squad_with_id(self) -> None:
        """A squad access keeps its squad id."""
        access = RefineryAccess(level=RefineryAccessLevel.SQUAD, squad_id=7)
        assert access.squad_id == 7

    @pytest.mark.parametrize("level", ["personal", "public"])
    def test_squad_id_outside_squad_rejected(self, level: str) -> None:
        """A squad id on a non-squad level is rejected."""
        with pytest.raises(ValidationError, match="squad_id is only allowed"):
            RefineryAccess.model_validate({"level": level, "squad_id": 1})

    def test_in_game_level_name_accepted(self) -> None:
        """The in-game enum name is normalized."""
        access = RefineryAccess.model_validate({"level": "ERefineryOrderAccessLevel::Squad"})
        assert access.level is RefineryAccessLevel.SQUAD

    def test_invalid_level_rejected(self) -> None:
        """An unknown level is rejected."""
        with pytest.raises(ValidationError):
            RefineryAccess.model_validate({"level": "team"})

    def test_extra_field_rejected(self) -> None:
        """Unknown fields are rejected."""
        with pytest.raises(ValidationError):
            RefineryAccess.model_validate({"level": "public", "other": 1})


class TestRefineryOrder:
    """Test suite for RefineryOrder limits."""

    def test_code_optional(self) -> None:
        """An order without code is valid."""
        assert RefineryOrder.model_validate(ORDER_BASE).code is None

    def test_upper_limits_accepted(self) -> None:
        """The game limits are accepted."""
        order = RefineryOrder.model_validate(
            {"slot": 255, "source": 65000, "refined": 65000, "duration": 64800}
        )
        assert order.slot == 255

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("slot", 256),
            ("slot", -1),
            ("source", 65001),
            ("source", -1),
            ("refined", 65001),
            ("refined", -1),
            ("duration", 64801),
            ("duration", -1),
        ],
    )
    def test_out_of_range_rejected(self, field: str, value: int) -> None:
        """Values outside the game limits are rejected."""
        with pytest.raises(ValidationError):
            RefineryOrder.model_validate({**ORDER_BASE, field: value})


class TestRefineryStorage:
    """Test suite for RefineryStorage limits."""

    def test_valid(self) -> None:
        """A storage from fs-sav validates."""
        storage = RefineryStorage.model_validate(REFINERY_DATA["storages"][0])
        assert storage.access.squad_id == 1
        assert storage.refined == 5309

    @pytest.mark.parametrize(("field", "value"), [("slot", 256), ("refined", 65001)])
    def test_out_of_range_rejected(self, field: str, value: int) -> None:
        """Values outside the game limits are rejected."""
        data = {"access": {"level": "public"}, "slot": 0, "refined": 0, field: value}
        with pytest.raises(ValidationError):
            RefineryStorage.model_validate(data)


class TestRefinery:
    """Test suite for Refinery."""

    def test_defaults(self) -> None:
        """An empty refinery has no access and empty lists."""
        refinery = Refinery()
        assert refinery.orders_access is None
        assert refinery.orders == []
        assert refinery.storages == []

    def test_round_trip(self) -> None:
        """The fs-sav payload round-trips through the model."""
        refinery = Refinery.model_validate(REFINERY_DATA)
        assert refinery.model_dump(exclude_none=True) == REFINERY_DATA


class TestStockpileRefinery:
    """Test suite for the refinery field on Stockpile."""

    def test_refinery_on_refinery_stockpile(self) -> None:
        """A main Refinery stockpile accepts refinery data."""
        stockpile = Stockpile(
            type=StockpileType.REFINERY, refinery=Refinery.model_validate(REFINERY_DATA)
        )
        assert stockpile.refinery is not None
        assert len(stockpile.refinery.orders) == 1

    def test_refinery_stockpile_without_refinery_valid(self) -> None:
        """A Refinery stockpile does not require refinery data."""
        assert Stockpile(type=StockpileType.REFINERY).refinery is None

    def test_refinery_on_seaport_rejected(self) -> None:
        """Refinery data on another stockpile type is rejected."""
        with pytest.raises(ValidationError, match="refinery is not allowed on 'Seaport'"):
            Stockpile(type=StockpileType.SEAPORT, refinery=Refinery())

    def test_refinery_on_reserve_rejected(self) -> None:
        """Refinery data on a reserve stockpile is rejected."""
        with pytest.raises(ValidationError, match="not allowed on reserve"):
            Stockpile(type=StockpileType.REFINERY, is_reserve=True, refinery=Refinery())
