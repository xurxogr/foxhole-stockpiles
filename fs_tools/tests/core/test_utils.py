"""Tests for fs_tools.core.utils (catalog loading, tool-path validation, pHash)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fs_tools.core.utils import load_catalog, validate_tool_path


class TestLoadCatalog:
    """Test suite for the load_catalog function.

    This class contains tests for loading and parsing catalog files,
    including valid files, error conditions, and partial data handling.
    """

    def test_load_valid_catalog(self, tmp_path: Path) -> None:
        """Test loading a valid catalog file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_data = [
            {
                "CodeName": "Rifle",
                "FactionVariant": "",
                "ItemCategory": "weapon",
                "Icon": "icons/rifle.png",
                "SubTypeIcon": "",
            },
            {
                "CodeName": "Ammo",
                "FactionVariant": "EFactionId::Colonials",
                "ItemCategory": "item",
                "Icon": "icons/ammo.png",
                "SubTypeIcon": "icons/ammo_sub.png",
            },
        ]

        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text(json.dumps(catalog_data))

        items = load_catalog(catalog_file)

        assert len(items) == 2
        assert items[0].code == "Rifle"
        assert items[0].faction.value == "neutral"
        assert items[1].code == "Ammo"
        assert items[1].faction.value == "Colonials"

    def test_load_nonexistent_catalog(self, tmp_path: Path) -> None:
        """Test loading a non-existent catalog file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "nonexistent.json"

        items = load_catalog(catalog_file)

        assert items == []

    def test_load_invalid_json_catalog(self, tmp_path: Path) -> None:
        """Test loading a catalog file with invalid JSON.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "invalid.json"
        catalog_file.write_text("{ invalid json content")

        items = load_catalog(catalog_file)

        assert items == []

    def test_load_catalog_with_partial_invalid_items(self, tmp_path: Path) -> None:
        """Test loading a catalog with some invalid items.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_data = [
            {
                "CodeName": "ValidItem",
                "FactionVariant": "",
                "ItemCategory": "item",
                "Icon": "icons/valid.png",
            },
            {
                # Missing required fields
                "InvalidField": "test",
            },
            {
                "CodeName": "AnotherValid",
                "FactionVariant": "EFactionId::Wardens",
                "ItemCategory": "weapon",
                "Icon": "icons/another.png",
            },
        ]

        catalog_file = tmp_path / "mixed.json"
        catalog_file.write_text(json.dumps(catalog_data))

        items = load_catalog(catalog_file)

        # The loader creates items even for invalid data, but with empty/default values
        assert len(items) == 3
        assert items[0].code == "ValidItem"
        assert items[1].code == ""  # Invalid item gets empty code
        assert items[2].code == "AnotherValid"

    def test_load_catalog_logs_warning_on_failed_items(self, tmp_path: Path) -> None:
        """Test that loading logs warning when items fail to convert.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_data = [
            {
                "CodeName": "ValidItem",
                "FactionVariant": "",
                "ItemCategory": "item",
                "Icon": "icons/valid.png",
            },
        ]

        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text(json.dumps(catalog_data))

        # Mock from_catalog to return None for some items
        with patch("fs_tools.core.utils.CatalogItem.from_catalog") as mock_from:
            mock_from.return_value = None  # Simulate failed conversion

            with patch("fs_tools.core.utils.logging.getLogger") as mock_logger_get:
                mock_logger = patch.object(mock_logger_get.return_value, "warning")
                with mock_logger:
                    items = load_catalog(catalog_file)

                    # Should have logged a warning
                    mock_logger_get.return_value.warning.assert_called()
                    assert items == []

    def test_load_empty_catalog(self, tmp_path: Path) -> None:
        """Test loading an empty catalog file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "empty.json"
        catalog_file.write_text("[]")

        items = load_catalog(catalog_file)

        assert items == []


class TestValidateToolPath:
    """Test suite for the validate_tool_path function."""

    def test_valid_tool_path(self, tmp_path: Path) -> None:
        """Test validation passes for a valid tool path.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        tool = tmp_path / "tool.exe"
        tool.touch()

        # Should not raise
        validate_tool_path(tool)

    def test_nonexistent_tool_raises_file_not_found(self, tmp_path: Path) -> None:
        """Test validation raises FileNotFoundError for nonexistent tool.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        tool = tmp_path / "nonexistent.exe"

        with pytest.raises(FileNotFoundError, match="Tool not found"):
            validate_tool_path(tool)

    def test_directory_raises_value_error(self, tmp_path: Path) -> None:
        """Test validation raises ValueError for directory path.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        with pytest.raises(ValueError, match="not a file"):
            validate_tool_path(tmp_path)

    def test_dangerous_chars_raise_value_error(self, tmp_path: Path) -> None:
        """Test validation raises ValueError for paths with dangerous characters.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Test each dangerous character
        dangerous_chars = [";", "|", "&", "`", "$"]

        for char in dangerous_chars:
            # Create a path with the dangerous character
            # Note: Some characters may not be valid in filenames on all systems
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.is_file", return_value=True),
                patch("pathlib.Path.resolve", return_value=Path(f"/path/to/tool{char}bad")),
            ):
                with pytest.raises(ValueError, match="Invalid character"):
                    validate_tool_path(tmp_path / "tool")

    def test_windows_invalid_extension_raises_value_error(self, tmp_path: Path) -> None:
        """Test validation raises ValueError for invalid extensions on Windows.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        tool = tmp_path / "tool.txt"
        tool.touch()

        with patch("fs_tools.core.utils.sys.platform", "win32"):
            with pytest.raises(ValueError, match="Invalid executable extension"):
                validate_tool_path(tool)

    def test_windows_valid_extensions(self, tmp_path: Path) -> None:
        """Test validation passes for valid Windows executable extensions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        valid_extensions = [".exe", ".bat", ".cmd", ".com"]

        with patch("fs_tools.core.utils.sys.platform", "win32"):
            for ext in valid_extensions:
                tool = tmp_path / f"tool{ext}"
                tool.touch()
                # Should not raise
                validate_tool_path(tool)
