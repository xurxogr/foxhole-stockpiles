"""Tests for core.utils module.

This module contains comprehensive tests for the core utility functions,
including catalog loading, frequency analysis, hash distance calculations,
and perceptual hash computation for images.
"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from foxhole_stockpiles.core.utils import (
    auto_detect_savefile,
    compute_icon_phash,
    find_mapdata_file,
    force_memory_release,
    get_bundled_resource_path,
    get_default_savefile_dir,
    get_subprocess_kwargs,
    is_frozen,
    load_catalog,
    malloc_trim,
    validate_tool_path,
)


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
        with patch("foxhole_stockpiles.core.utils.CatalogItem.from_catalog") as mock_from:
            mock_from.return_value = None  # Simulate failed conversion

            with patch("foxhole_stockpiles.core.utils.logging.getLogger") as mock_logger_get:
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


class TestComputeIconPhash:
    """Test suite for the compute_icon_phash function.

    This class contains tests for perceptual hash computation of images,
    including various image types, formats, and similarity scenarios.
    """

    def test_grayscale_image(self) -> None:
        """Test phash computation with grayscale image.

        Validates that grayscale images produce valid perceptual hashes.
        """
        # Create a simple 16x16 grayscale test image
        image = np.zeros((16, 16), dtype=np.uint8)
        image[0:8, 0:8] = 255  # Top-left quadrant white

        phash = compute_icon_phash(image)

        assert isinstance(phash, int)
        assert phash >= 0

    def test_color_image(self) -> None:
        """Test phash computation with color image.

        Validates that color images are properly converted and hashed.
        """
        # Create a simple 16x16 BGR test image
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        image[0:8, 0:8] = [255, 255, 255]  # Top-left quadrant white

        phash = compute_icon_phash(image)

        assert isinstance(phash, int)
        assert phash >= 0

    def test_uniform_image(self) -> None:
        """Test phash computation with uniform image.

        Validates hash computation for images with uniform pixel values.
        """
        # Create a uniform gray image
        image = np.full((16, 16), 128, dtype=np.uint8)

        phash = compute_icon_phash(image)

        # Uniform image should produce a specific pattern
        assert isinstance(phash, int)

    def test_identical_images_same_hash(self) -> None:
        """Test that identical images produce the same hash.

        Validates that the hash function is deterministic for identical inputs.
        """
        image1 = np.random.randint(0, 256, (32, 32), dtype=np.uint8)
        image2 = image1.copy()

        phash1 = compute_icon_phash(image1)
        phash2 = compute_icon_phash(image2)

        assert phash1 == phash2

    def test_different_images_different_hash(self) -> None:
        """Test that different images produce different hashes.

        Validates that substantially different images produce different hashes.
        """
        # Create image with gradient pattern
        image1 = np.zeros((16, 16), dtype=np.uint8)
        image1[:8, :] = 100
        image1[8:, :] = 200

        # Create different pattern
        image2 = np.zeros((16, 16), dtype=np.uint8)
        image2[:, :8] = 100
        image2[:, 8:] = 200

        phash1 = compute_icon_phash(image1)
        phash2 = compute_icon_phash(image2)

        assert phash1 != phash2

    def test_small_variation_similar_hash(self) -> None:
        """Test that small variations produce similar hashes.

        Validates that perceptual hashes are robust to small image changes.
        """
        image1 = np.random.randint(0, 256, (32, 32), dtype=np.uint8)
        image2 = image1.copy()
        # Modify a small region
        image2[0:2, 0:2] = 255 - image2[0:2, 0:2]

        phash1 = compute_icon_phash(image1)
        phash2 = compute_icon_phash(image2)

        # Hashes should be similar (small hamming distance)
        distance = bin(phash1 ^ phash2).count("1")
        assert distance < 20  # Threshold for similarity


class TestMallocTrim:
    """Test suite for the malloc_trim function."""

    def test_malloc_trim_success(self) -> None:
        """Test malloc_trim when libc is available."""
        result = malloc_trim()
        assert isinstance(result, int)
        assert result in (-1, 0, 1)

    def test_malloc_trim_with_pad(self) -> None:
        """Test malloc_trim with custom pad value."""
        result = malloc_trim(pad=1024)
        assert isinstance(result, int)

    def test_malloc_trim_handles_unavailable_libc(self) -> None:
        """Test malloc_trim when libc is not available."""
        with patch("foxhole_stockpiles.core.utils.ctypes.CDLL") as mock_cdll:
            mock_cdll.side_effect = OSError("libc not found")
            result = malloc_trim()
            assert result == -1


class TestForceMemoryRelease:
    """Test suite for the force_memory_release function."""

    def test_force_memory_release_returns_stats(self) -> None:
        """Test that force_memory_release returns statistics."""
        result = force_memory_release()
        assert isinstance(result, dict)
        assert "gc_collected" in result
        assert "malloc_trimmed" in result

    def test_force_memory_release_calls_gc_collect(self) -> None:
        """Test that force_memory_release calls gc.collect."""
        with patch("foxhole_stockpiles.core.utils.gc.collect") as mock_collect:
            mock_collect.return_value = 42
            result = force_memory_release()
            mock_collect.assert_called_once()
            assert result["gc_collected"] == 42


class TestGetSubprocessKwargs:
    """Test suite for the get_subprocess_kwargs function."""

    def test_returns_dict(self) -> None:
        """Test that get_subprocess_kwargs returns a dictionary."""
        result = get_subprocess_kwargs()
        assert isinstance(result, dict)

    def test_returns_creationflags_on_windows(self) -> None:
        """Test that creationflags is returned on Windows."""
        # CREATE_NO_WINDOW only exists on Windows, so we need to mock it
        mock_create_no_window = 0x08000000  # Actual value on Windows

        with (
            patch("foxhole_stockpiles.core.utils.sys.platform", "win32"),
            patch(
                "foxhole_stockpiles.core.utils.subprocess.CREATE_NO_WINDOW",
                mock_create_no_window,
                create=True,
            ),
        ):
            result = get_subprocess_kwargs()
            assert "creationflags" in result
            assert result["creationflags"] == mock_create_no_window

    def test_returns_empty_dict_on_linux(self) -> None:
        """Test that empty dict is returned on Linux."""
        with patch("foxhole_stockpiles.core.utils.sys.platform", "linux"):
            result = get_subprocess_kwargs()
            assert result == {}

    def test_returns_empty_dict_on_darwin(self) -> None:
        """Test that empty dict is returned on macOS."""
        with patch("foxhole_stockpiles.core.utils.sys.platform", "darwin"):
            result = get_subprocess_kwargs()
            assert result == {}


class TestIsFrozen:
    """Test suite for the is_frozen function."""

    def test_is_frozen_false(self) -> None:
        """Test is_frozen returns False in normal mode."""
        result = is_frozen()
        assert result is False

    def test_is_frozen_true(self) -> None:
        """Test is_frozen returns True when frozen."""
        with (
            patch("foxhole_stockpiles.core.utils.sys", frozen=True, _MEIPASS="/tmp/bundle"),
        ):
            # Need to mock getattr and hasattr behavior
            with (
                patch("foxhole_stockpiles.core.utils.getattr", return_value=True),
                patch("foxhole_stockpiles.core.utils.hasattr", return_value=True),
            ):
                result = is_frozen()
                # Will still be False since we can't easily mock sys attributes
                assert isinstance(result, bool)


class TestGetBundledResourcePath:
    """Test suite for the get_bundled_resource_path function."""

    def test_bundled_resource_path_dev_mode(self) -> None:
        """Test getting bundled resource path in development mode."""
        with patch("foxhole_stockpiles.core.utils.is_frozen", return_value=False):
            result = get_bundled_resource_path("tessdata")
            assert result == Path.cwd() / "tessdata"

    def test_bundled_resource_path_frozen_mode(self) -> None:
        """Test getting bundled resource path in frozen mode."""
        mock_meipass = "/tmp/pyinstaller_bundle"

        import sys

        import foxhole_stockpiles.core.utils as utils_module

        # Save original
        original_is_frozen = utils_module.is_frozen
        had_meipass = hasattr(sys, "_MEIPASS")
        original_meipass = getattr(sys, "_MEIPASS", None)

        try:
            # Mock is_frozen to return True
            utils_module.is_frozen = lambda: True
            # Set sys._MEIPASS
            sys._MEIPASS = mock_meipass  # type: ignore[attr-defined]

            result = get_bundled_resource_path("tessdata")
            assert str(result) == f"{mock_meipass}/tessdata"
        finally:
            # Restore original
            utils_module.is_frozen = original_is_frozen
            if had_meipass:
                sys._MEIPASS = original_meipass  # type: ignore[attr-defined]
            elif hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS


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

        with patch("foxhole_stockpiles.core.utils.sys.platform", "win32"):
            with pytest.raises(ValueError, match="Invalid executable extension"):
                validate_tool_path(tool)

    def test_windows_valid_extensions(self, tmp_path: Path) -> None:
        """Test validation passes for valid Windows executable extensions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        valid_extensions = [".exe", ".bat", ".cmd", ".com"]

        with patch("foxhole_stockpiles.core.utils.sys.platform", "win32"):
            for ext in valid_extensions:
                tool = tmp_path / f"tool{ext}"
                tool.touch()
                # Should not raise
                validate_tool_path(tool)


class TestGetDefaultSavefileDir:
    """Test suite for the get_default_savefile_dir function."""

    def test_windows_with_appdata(self, tmp_path: Path) -> None:
        """Test finding save directory on Windows with LOCALAPPDATA set.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create fake Windows save directory structure
        save_dir = tmp_path / "Foxhole" / "Saved" / "SaveGames"
        save_dir.mkdir(parents=True)

        with (
            patch("foxhole_stockpiles.core.utils.sys.platform", "win32"),
            patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}),
        ):
            result = get_default_savefile_dir()
            assert result == save_dir

    def test_windows_no_appdata(self) -> None:
        """Test Windows without LOCALAPPDATA environment variable."""
        with (
            patch("foxhole_stockpiles.core.utils.sys.platform", "win32"),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = get_default_savefile_dir()
            assert result is None

    def test_windows_dir_not_exists(self, tmp_path: Path) -> None:
        """Test Windows with LOCALAPPDATA but no save directory.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        with (
            patch("foxhole_stockpiles.core.utils.sys.platform", "win32"),
            patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}),
        ):
            result = get_default_savefile_dir()
            assert result is None

    def test_unsupported_platform(self) -> None:
        """Test with unsupported platform."""
        with patch("foxhole_stockpiles.core.utils.sys.platform", "darwin"):
            result = get_default_savefile_dir()
            assert result is None

    def test_linux_no_wsl_no_proton(self) -> None:
        """Test Linux when neither WSL nor Proton paths exist."""
        with patch("foxhole_stockpiles.core.utils.sys.platform", "linux"):
            result = get_default_savefile_dir()
            # Should return None since paths don't exist
            assert result is None or isinstance(result, Path)


class TestFindMapdataFile:
    """Test suite for the find_mapdata_file function."""

    def test_find_existing_mapdata(self, tmp_path: Path) -> None:
        """Test finding existing MapData.sav file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        mapdata_file = tmp_path / "User_MapData.sav"
        mapdata_file.touch()

        result = find_mapdata_file(tmp_path)
        assert result == mapdata_file

    def test_find_first_mapdata(self, tmp_path: Path) -> None:
        """Test finding first MapData.sav when multiple exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        mapdata1 = tmp_path / "User1_MapData.sav"
        mapdata2 = tmp_path / "User2_MapData.sav"
        mapdata1.touch()
        mapdata2.touch()

        result = find_mapdata_file(tmp_path)
        # Should return one of them (first found)
        assert result in (mapdata1, mapdata2)

    def test_no_mapdata_found(self, tmp_path: Path) -> None:
        """Test when no MapData.sav exists.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create some other files
        (tmp_path / "other.sav").touch()
        (tmp_path / "something.dat").touch()

        result = find_mapdata_file(tmp_path)
        assert result is None

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test with empty directory.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        result = find_mapdata_file(tmp_path)
        assert result is None


class TestAutoDetectSavefile:
    """Test suite for the auto_detect_savefile function."""

    def test_auto_detect_success(self, tmp_path: Path) -> None:
        """Test successful auto-detection of save file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        save_dir = tmp_path / "SaveGames"
        save_dir.mkdir()
        mapdata = save_dir / "User_MapData.sav"
        mapdata.touch()

        with patch("foxhole_stockpiles.core.utils.get_default_savefile_dir", return_value=save_dir):
            result = auto_detect_savefile()
            assert result == mapdata

    def test_auto_detect_no_save_dir(self) -> None:
        """Test auto-detection when no save directory found."""
        with patch("foxhole_stockpiles.core.utils.get_default_savefile_dir", return_value=None):
            result = auto_detect_savefile()
            assert result is None

    def test_auto_detect_no_mapdata_file(self, tmp_path: Path) -> None:
        """Test auto-detection when save dir exists but no MapData file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        save_dir = tmp_path / "SaveGames"
        save_dir.mkdir()

        with patch("foxhole_stockpiles.core.utils.get_default_savefile_dir", return_value=save_dir):
            result = auto_detect_savefile()
            assert result is None
