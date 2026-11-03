"""Tests for enums.capture_mode module."""

from foxhole_stockpiles.enums.capture_mode import CaptureMode


class TestClipModeEnum:
    """Test suite for CaptureMode enum values."""

    def test_enum_values(self) -> None:
        """Test that all CaptureMode values are correctly defined."""
        assert CaptureMode.MANUAL.value == "manual"
        assert CaptureMode.MONITOR.value == "monitor"

    def test_is_str_enum(self) -> None:
        """Test that CaptureMode members behave as their string value."""
        assert isinstance(CaptureMode.MANUAL, str)
        assert str(CaptureMode.MANUAL) == "manual"
        assert str(CaptureMode.MONITOR) == "monitor"


class TestFromString:
    """Test suite for CaptureMode.from_string."""

    def test_monitor_exact(self) -> None:
        """Test that 'monitor' resolves to MONITOR."""
        assert CaptureMode.from_string("monitor") is CaptureMode.MONITOR

    def test_manual_exact(self) -> None:
        """Test that 'manual' resolves to MANUAL."""
        assert CaptureMode.from_string("manual") is CaptureMode.MANUAL

    def test_case_and_whitespace_insensitive(self) -> None:
        """Test that surrounding whitespace and case are normalized."""
        assert CaptureMode.from_string("  MONITOR  ") is CaptureMode.MONITOR
        assert CaptureMode.from_string("Manual") is CaptureMode.MANUAL

    def test_none_defaults_to_manual(self) -> None:
        """Test that None defaults to MANUAL."""
        assert CaptureMode.from_string(None) is CaptureMode.MANUAL

    def test_empty_defaults_to_manual(self) -> None:
        """Test that an empty string defaults to MANUAL."""
        assert CaptureMode.from_string("") is CaptureMode.MANUAL

    def test_unknown_defaults_to_manual(self) -> None:
        """Test that an unrecognized value defaults to MANUAL."""
        assert CaptureMode.from_string("nonsense") is CaptureMode.MANUAL

    def test_default_argument_is_manual(self) -> None:
        """Test that calling with no argument defaults to MANUAL."""
        assert CaptureMode.from_string() is CaptureMode.MANUAL
