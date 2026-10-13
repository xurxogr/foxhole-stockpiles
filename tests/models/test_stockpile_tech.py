"""Tests for the StockpileTech model and its link to Stockpile."""

from typing import Any

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_tech import StockpileTech

FORT_BASE_TECH: dict[str, Any] = {
    "ProvisionalGarrison": 100,
    "SmallGarrison": 100,
    "LargeGarrison": 70,
    "T1Garrison": 100,
    "T2Garrison": 100,
    "T3Garrison": 0,
    "ArtilleryGarrison": 0,
    "T1SupportBunkers": 0,
    "T3SupportBunkers": 0,
    "Deployment": 0,
    "AdvancedBunkers": 0,
}


class TestStockpileTech:
    """Test suite for StockpileTech."""

    def test_pascal_case_input(self) -> None:
        """The PascalCase keys emitted by fs-sav map onto the fields."""
        tech = StockpileTech.model_validate(FORT_BASE_TECH)
        assert tech.large_garrison == 70
        assert tech.t1_support_bunkers == 0
        assert tech.industry is None

    def test_snake_case_input(self) -> None:
        """Field names are also accepted."""
        assert StockpileTech(t2_garrison=50).t2_garrison == 50

    def test_dump_skips_absent_slots(self) -> None:
        """Slots the base does not have are dropped with exclude_none."""
        tech = StockpileTech.model_validate({"ProvisionalGarrison": 100})
        assert tech.model_dump(exclude_none=True) == {"provisional_garrison": 100}

    @pytest.mark.parametrize("value", [-1, 101])
    def test_out_of_range_rejected(self, value: int) -> None:
        """Progress outside 0-100 is rejected."""
        with pytest.raises(ValidationError):
            StockpileTech.model_validate({"Industry": value})

    def test_unknown_slot_rejected(self) -> None:
        """Unknown slots are rejected."""
        with pytest.raises(ValidationError):
            StockpileTech.model_validate({"Shipyard": 100})


class TestStockpileTypeHasTech:
    """Test suite for StockpileType.has_tech."""

    @pytest.mark.parametrize(
        "value",
        [StockpileType.BUNKER_BASE_2, StockpileType.TOWN_BASE_1, StockpileType.SAFE_HOUSE],
    )
    def test_bases(self, value: str) -> None:
        """Bases with a tech tree are recognized."""
        assert StockpileType.has_tech(value)

    @pytest.mark.parametrize("value", [StockpileType.SEAPORT, StockpileType.REFINERY, "NewBase"])
    def test_non_bases(self, value: str) -> None:
        """Structures without a tech tree and unknown types are not."""
        assert not StockpileType.has_tech(value)


class TestStockpileTechField:
    """Test suite for the tech field on Stockpile."""

    def test_tech_on_bunker_base(self) -> None:
        """A main bunker base accepts tech data."""
        stockpile = Stockpile(
            type=StockpileType.BUNKER_BASE_2, tech=StockpileTech.model_validate(FORT_BASE_TECH)
        )
        assert stockpile.tech is not None
        assert stockpile.tech.t2_garrison == 100

    def test_base_without_tech_valid(self) -> None:
        """A base does not require tech data."""
        assert Stockpile(type=StockpileType.BUNKER_BASE_1).tech is None

    def test_tech_on_seaport_rejected(self) -> None:
        """Tech data on a structure without tech tree is rejected."""
        with pytest.raises(ValidationError, match="tech is not allowed on 'Seaport'"):
            Stockpile(type=StockpileType.SEAPORT, tech=StockpileTech())

    def test_tech_on_reserve_rejected(self) -> None:
        """Tech data on a reserve stockpile is rejected."""
        with pytest.raises(ValidationError, match="not allowed on reserve"):
            Stockpile(type=StockpileType.BUNKER_BASE_1, is_reserve=True, tech=StockpileTech())
