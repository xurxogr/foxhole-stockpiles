"""Tests for enums.clip_mode module."""

from foxhole_stockpiles.enums.clip_mode import ClipMode


class TestClipModeEnum:
    """Test suite for ClipMode enum values."""

    def test_enum_values(self) -> None:
        """Test that all ClipMode values are correctly defined."""
        assert ClipMode.MANUAL.value == "manual"
        assert ClipMode.MONITOR.value == "monitor"

    def test_is_str_enum(self) -> None:
        """Test that ClipMode members behave as their string value."""
        assert isinstance(ClipMode.MANUAL, str)
        assert str(ClipMode.MANUAL) == "manual"
        assert str(ClipMode.MONITOR) == "monitor"


class TestFromString:
    """Test suite for ClipMode.from_string."""

    def test_monitor_exact(self) -> None:
        """Test that 'monitor' resolves to MONITOR."""
        assert ClipMode.from_string("monitor") is ClipMode.MONITOR

    def test_manual_exact(self) -> None:
        """Test that 'manual' resolves to MANUAL."""
        assert ClipMode.from_string("manual") is ClipMode.MANUAL

    def test_case_and_whitespace_insensitive(self) -> None:
        """Test that surrounding whitespace and case are normalized."""
        assert ClipMode.from_string("  MONITOR  ") is ClipMode.MONITOR
        assert ClipMode.from_string("Manual") is ClipMode.MANUAL

    def test_none_defaults_to_manual(self) -> None:
        """Test that None defaults to MANUAL."""
        assert ClipMode.from_string(None) is ClipMode.MANUAL

    def test_empty_defaults_to_manual(self) -> None:
        """Test that an empty string defaults to MANUAL."""
        assert ClipMode.from_string("") is ClipMode.MANUAL

    def test_unknown_defaults_to_manual(self) -> None:
        """Test that an unrecognized value defaults to MANUAL."""
        assert ClipMode.from_string("nonsense") is ClipMode.MANUAL

    def test_default_argument_is_manual(self) -> None:
        """Test that calling with no argument defaults to MANUAL."""
        assert ClipMode.from_string() is ClipMode.MANUAL
