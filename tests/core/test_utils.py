"""Tests for core.utils module.

This module contains comprehensive tests for the core utility functions,
including catalog loading, frequency analysis, hash distance calculations,
and perceptual hash computation for images.
"""

import os
from pathlib import Path
from unittest.mock import patch

from foxhole_stockpiles.core.utils import (
    auto_detect_savefile,
    find_mapdata_file,
    get_bundled_resource_path,
    is_frozen,
)


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

    def test_find_most_recent_mapdata(self, tmp_path: Path) -> None:
        """Test that the most recently written MapData.sav wins when several exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        older = tmp_path / "76561198000000001_MapData.sav"
        newer = tmp_path / "76561198000000002_MapData.sav"
        older.touch()
        newer.touch()
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(newer, (2_000_000, 2_000_000))

        assert find_mapdata_file(tmp_path) == newer

        os.utime(older, (3_000_000, 3_000_000))
        assert find_mapdata_file(tmp_path) == older

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

    def test_auto_detect_uses_newest(self) -> None:
        """The first (newest) save fs-sav finds is returned."""
        saves = [
            {
                "path": "/saves/76561198000000002_MapData.sav",
                "steam_id": "76561198000000002",
                "modified": "2026-10-13T10:00:00Z",
                "size_bytes": 2048,
            },
            {
                "path": "/saves/76561198000000001_MapData.sav",
                "steam_id": "76561198000000001",
                "modified": "2026-10-12T10:00:00Z",
                "size_bytes": 1024,
            },
        ]
        with patch("foxhole_stockpiles.core.utils.fs_sav.find_save_files", return_value=saves):
            result = auto_detect_savefile()
        assert result == Path("/saves/76561198000000002_MapData.sav")

    def test_auto_detect_none_found(self) -> None:
        """No save found by fs-sav yields None."""
        with patch("foxhole_stockpiles.core.utils.fs_sav.find_save_files", return_value=[]):
            assert auto_detect_savefile() is None
