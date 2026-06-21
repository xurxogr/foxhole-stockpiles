"""Tests for settings.sections.scanner module.

This module contains comprehensive tests for the ScannerSettings model,
including field validation, model validation, and configuration retrieval.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings


class TestScannerSettingsInitialization:
    """Test suite for ScannerSettings initialization.

    This class contains tests for creating ScannerSettings instances
    with various parameter combinations.
    """

    def test_initialization_with_defaults(self) -> None:
        """Test initialization with default values."""
        config = ScannerSettings()

        assert config.database_path is None
        assert config.capture_key is None
        assert config.early_exit_threshold == 0.0
        assert config.confidence_gap == 0.0
        assert config.screenshots_folder == ""

    def test_initialization_with_custom_values(self, tmp_path: Path) -> None:
        """Test initialization with custom values.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_file = tmp_path / "custom.h5"

        config = ScannerSettings(
            database_path=db_file,
            capture_key="F9",
            early_exit_threshold=0.99,
            confidence_gap=0.15,
            screenshots_folder="screenshots",
        )

        assert config.database_path == db_file
        assert config.capture_key == "F9"
        assert config.early_exit_threshold == 0.99
        assert config.confidence_gap == 0.15
        assert config.screenshots_folder == "screenshots"


class TestDatabasePath:
    """Test suite for database_path field.

    This class contains tests for the database_path field including None handling.
    """

    def test_database_path_with_path(self, tmp_path: Path) -> None:
        """Test database_path accepts a Path object.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_file = tmp_path / "valid.h5"

        config = ScannerSettings(database_path=db_file)

        assert config.database_path == db_file

    def test_database_path_with_none(self) -> None:
        """Test database_path accepts None (for commands that don't use it)."""
        config = ScannerSettings(database_path=None)

        assert config.database_path is None

    def test_database_path_default_is_none(self) -> None:
        """Test database_path defaults to None when not provided."""
        config = ScannerSettings()

        assert config.database_path is None


class TestFieldConstraints:
    """Test suite for Pydantic field constraints.

    This class contains tests for built-in Pydantic constraints
    like ge, le on various fields.
    """

    def test_early_exit_threshold_below_minimum(self) -> None:
        """Test early_exit_threshold validation fails below 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            ScannerSettings(early_exit_threshold=-0.1)

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_early_exit_threshold_above_maximum(self) -> None:
        """Test early_exit_threshold validation fails above 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            ScannerSettings(early_exit_threshold=1.5)

        assert "less than or equal to 1" in str(exc_info.value)

    def test_confidence_gap_below_minimum(self) -> None:
        """Test that confidence_gap below minimum (< 0.0) raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ScannerSettings(confidence_gap=-0.1)

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_confidence_gap_above_maximum(self) -> None:
        """Test that confidence_gap above maximum (> 1.0) raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ScannerSettings(confidence_gap=1.5)

        assert "less than or equal to 1" in str(exc_info.value)

    def test_confidence_gap_valid_values(self) -> None:
        """Test that valid confidence_gap values are accepted."""
        # Test boundary values
        config_min = ScannerSettings(confidence_gap=0.0)
        assert config_min.confidence_gap == 0.0

        config_mid = ScannerSettings(confidence_gap=0.15)
        assert config_mid.confidence_gap == 0.15

        config_max = ScannerSettings(confidence_gap=1.0)
        assert config_max.confidence_gap == 1.0


class TestModelConfigSettings:
    """Test suite for model configuration settings.

    This class contains tests for Pydantic model configuration
    like str_strip_whitespace, validate_assignment, and extra fields.
    """

    def test_str_strip_whitespace(self) -> None:
        """Test that string fields have whitespace stripped."""
        config = ScannerSettings(capture_key="  F9  ")

        assert config.capture_key == "F9"

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            ScannerSettings(unknown_field="value")  # type: ignore

        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_validate_assignment(self) -> None:
        """Test that assignment validation is enabled."""
        config = ScannerSettings()

        # Try to assign invalid value after creation
        with pytest.raises(ValidationError):
            config.confidence_gap = 1.5  # Above maximum
