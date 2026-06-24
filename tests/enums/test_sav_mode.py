"""Tests for enums.sav_mode module."""

from foxhole_stockpiles.enums.sav_mode import SavMode


class TestSavModeEnum:
    """Test suite for SavMode enum values."""

    def test_enum_values(self) -> None:
        """Test that all SavMode values are correctly defined."""
        assert SavMode.MANUAL.value == "manual"
        assert SavMode.MONITOR.value == "monitor"

    def test_is_str_enum(self) -> None:
        """Test that SavMode members behave as their string value."""
        assert isinstance(SavMode.MANUAL, str)
        assert str(SavMode.MANUAL) == "manual"
        assert str(SavMode.MONITOR) == "monitor"


class TestFromString:
    """Test suite for SavMode.from_string."""

    def test_monitor_exact(self) -> None:
        """Test that 'monitor' resolves to MONITOR."""
        assert SavMode.from_string("monitor") is SavMode.MONITOR

    def test_manual_exact(self) -> None:
        """Test that 'manual' resolves to MANUAL."""
        assert SavMode.from_string("manual") is SavMode.MANUAL

    def test_case_and_whitespace_insensitive(self) -> None:
        """Test that surrounding whitespace and case are normalized."""
        assert SavMode.from_string("  MONITOR  ") is SavMode.MONITOR
        assert SavMode.from_string("Manual") is SavMode.MANUAL

    def test_none_defaults_to_manual(self) -> None:
        """Test that None defaults to MANUAL."""
        assert SavMode.from_string(None) is SavMode.MANUAL

    def test_empty_defaults_to_manual(self) -> None:
        """Test that an empty string defaults to MANUAL."""
        assert SavMode.from_string("") is SavMode.MANUAL

    def test_unknown_defaults_to_manual(self) -> None:
        """Test that an unrecognized value defaults to MANUAL."""
        assert SavMode.from_string("nonsense") is SavMode.MANUAL

    def test_default_argument_is_manual(self) -> None:
        """Test that calling with no argument defaults to MANUAL."""
        assert SavMode.from_string() is SavMode.MANUAL
