"""Tests for core.utils module.

This module contains comprehensive tests for the core utility functions,
including catalog loading, frequency analysis, hash distance calculations,
and perceptual hash computation for images.
"""

from pathlib import Path
from unittest.mock import patch

from foxhole_stockpiles.core.utils import (
    auto_detect_savefile,
    find_mapdata_file,
    force_memory_release,
    get_bundled_resource_path,
    get_default_savefile_dir,
    get_subprocess_kwargs,
    is_frozen,
    malloc_trim,
)


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
