"""Tests for fs_tools.template_db.template_manager module.

This module contains comprehensive tests for the TemplateManager class,
which handles template database loading, caching, and management for
different screen resolutions.
"""

from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np
import pytest

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.icon_template import IconTemplate
from fs_tools.template_db.template_database import TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager


def create_hdf5_database(
    db_path: Path, databases: dict[SupportedResolution, TemplateDatabase]
) -> None:
    """Create an HDF5 database file for testing.

    Args:
        db_path (Path): Path where the HDF5 database will be created.
        databases (dict[SupportedResolution, TemplateDatabase]): Dict of resolution to database.
    """
    # Write via the production writer so tests exercise the real on-disk format.
    TemplateManager.save_databases_to_hdf5(databases, db_path, workers=1)


class TestTemplateManagerInitialization:
    """Test suite for TemplateManager initialization.

    This class contains tests for proper initialization of the TemplateManager
    including path handling, cache initialization, and initial state validation.
    """

    def test_init_with_path(self, tmp_path: Path) -> None:
        """Test initializing TemplateManager with a database path.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        assert manager.database_path == db_path
        assert manager.current_resolution is None

    def test_init_creates_empty_cache(self, tmp_path: Path) -> None:
        """Test that initialization creates empty database cache.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        assert manager.current_resolution is None


class TestLoadDatabase:
    """Test suite for TemplateManager.load_database method.

    This class contains tests for database loading functionality including
    new database loading, cache handling, error conditions, and file corruption.
    """

    async def test_load_new_database(self, tmp_path: Path) -> None:
        """Test loading a database for a new resolution.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create a real database file
        real_db = TemplateDatabase(SupportedResolution.R_1080)
        databases = {SupportedResolution.R_1080: real_db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)

        with patch("logging.Logger.debug") as mock_log:
            db = await manager.load_database(SupportedResolution.R_1080)

        assert db is not None
        mock_log.assert_called()

    async def test_load_cached_database(self, tmp_path: Path) -> None:
        """Test loading a database that's already cached.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create a real database
        real_db = TemplateDatabase(SupportedResolution.R_1080)

        # Create database file
        databases = {SupportedResolution.R_1080: real_db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)

        # Load it once to cache it
        await manager.load_database(SupportedResolution.R_1080)

        # Load it again - should use cache
        with patch("logging.Logger.debug"):
            db = await manager.load_database(SupportedResolution.R_1080)

        assert db is not None

    async def test_load_missing_resolution(self, tmp_path: Path) -> None:
        """Test loading a resolution that doesn't exist in the database.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with only one resolution
        real_db = TemplateDatabase(SupportedResolution.R_1080)
        databases = {SupportedResolution.R_1080: real_db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)

        # Try to load a different resolution
        with pytest.raises(ValueError):
            await manager.load_database(SupportedResolution.R_720)

    async def test_load_corrupted_database(self, tmp_path: Path) -> None:
        """Test handling of corrupted database file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "corrupted.h5"
        db_path.write_text("corrupted data")

        manager = TemplateManager(db_path)

        # Should raise ValueError for corrupted/invalid database file
        with pytest.raises(ValueError):
            await manager.load_database(SupportedResolution.R_1080)

    async def test_load_nonexistent_database(self, tmp_path: Path) -> None:
        """Test loading a database that doesn't exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "nonexistent.h5"

        manager = TemplateManager(db_path)

        # Should raise FileNotFoundError for missing database
        with pytest.raises(FileNotFoundError) as exc_info:
            await manager.load_database(SupportedResolution.R_1080)

        assert "Template database not found" in str(exc_info.value)

    async def test_load_wrong_version_database(self, tmp_path: Path) -> None:
        """Test loading a database with wrong version.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "wrong_version.h5"

        # Create an h5 file with wrong version
        with h5py.File(str(db_path), "w") as f:
            f.attrs["version"] = 999  # Wrong version
            f.attrs["format"] = "hdf5"
            f.attrs["resolutions"] = [SupportedResolution.R_1080.value]

        manager = TemplateManager(db_path)

        # Should raise ValueError for version mismatch
        with pytest.raises(ValueError) as exc_info:
            await manager.load_database(SupportedResolution.R_1080)

        assert "version 999 does not match" in str(exc_info.value)


class TestTemplateManagerRepr:
    """Test suite for TemplateManager.__repr__ method."""

    def test_repr(self, tmp_path: Path) -> None:
        """Test string representation of TemplateManager.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        repr_str = repr(manager)

        assert "TemplateManager" in repr_str
        assert str(db_path) in repr_str
        assert "current_resolution" in repr_str


class TestLRUCache:
    """Test suite for TemplateManager LRU cache functionality."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the shared cache before each test."""
        TemplateManager._shared_databases.clear()

    async def test_no_caching_with_size_zero(self, tmp_path: Path) -> None:
        """Test that cache_size=0 disables caching completely.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with two resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with cache_size=0
        manager = TemplateManager(db_path, cache_size=0)

        # Load first resolution
        db1 = await manager.load_database(SupportedResolution.R_1080)
        assert db1 is not None

        # Cache should be empty
        assert len(TemplateManager._shared_databases) == 0

        # Load second resolution
        db2 = await manager.load_database(SupportedResolution.R_1440)
        assert db2 is not None

        # Cache should still be empty
        assert len(TemplateManager._shared_databases) == 0

    async def test_lru_cache_with_size_one(self, tmp_path: Path) -> None:
        """Test that cache_size=1 keeps only the most recently used resolution.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with three resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_2160 = TemplateDatabase(SupportedResolution.R_2160)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_2160: db_2160,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with cache_size=1
        manager = TemplateManager(db_path, cache_size=1)

        # Load first resolution
        await manager.load_database(SupportedResolution.R_1080)
        assert len(TemplateManager._shared_databases) == 1
        assert (db_path, SupportedResolution.R_1080) in TemplateManager._shared_databases

        # Load second resolution - should evict first
        await manager.load_database(SupportedResolution.R_1440)
        assert len(TemplateManager._shared_databases) == 1
        assert (db_path, SupportedResolution.R_1080) not in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1440) in TemplateManager._shared_databases

        # Load third resolution - should evict second
        await manager.load_database(SupportedResolution.R_2160)
        assert len(TemplateManager._shared_databases) == 1
        assert (db_path, SupportedResolution.R_1440) not in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_2160) in TemplateManager._shared_databases

    async def test_lru_cache_with_size_two(self, tmp_path: Path) -> None:
        """Test that cache_size=2 keeps the two most recently used resolutions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with three resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_2160 = TemplateDatabase(SupportedResolution.R_2160)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_2160: db_2160,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with cache_size=2
        manager = TemplateManager(db_path, cache_size=2)

        # Load first two resolutions
        await manager.load_database(SupportedResolution.R_1080)
        await manager.load_database(SupportedResolution.R_1440)
        assert len(TemplateManager._shared_databases) == 2

        # Load third resolution - should evict first (LRU)
        await manager.load_database(SupportedResolution.R_2160)
        assert len(TemplateManager._shared_databases) == 2
        assert (db_path, SupportedResolution.R_1080) not in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1440) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_2160) in TemplateManager._shared_databases

        # Access R_1440 again to make it most recently used
        await manager.load_database(SupportedResolution.R_1440)
        assert len(TemplateManager._shared_databases) == 2

        # Load R_1080 - should evict R_2160 (now LRU)
        await manager.load_database(SupportedResolution.R_1080)
        assert len(TemplateManager._shared_databases) == 2
        assert (db_path, SupportedResolution.R_2160) not in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1440) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1080) in TemplateManager._shared_databases

    async def test_default_cache_size(self, tmp_path: Path) -> None:
        """Test that default cache_size allows caching all resolutions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with four resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_2160 = TemplateDatabase(SupportedResolution.R_2160)
        db_1536 = TemplateDatabase(SupportedResolution.R_1536)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_2160: db_2160,
            SupportedResolution.R_1536: db_1536,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with default cache_size (16)
        manager = TemplateManager(db_path)

        # Load all four resolutions
        await manager.load_database(SupportedResolution.R_1080)
        await manager.load_database(SupportedResolution.R_1440)
        await manager.load_database(SupportedResolution.R_2160)
        await manager.load_database(SupportedResolution.R_1536)

        # All should be cached
        assert len(TemplateManager._shared_databases) == 4
        assert (db_path, SupportedResolution.R_1080) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1440) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_2160) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1536) in TemplateManager._shared_databases

    async def test_cache_hit_updates_lru_order(self, tmp_path: Path) -> None:
        """Test that accessing a cached entry moves it to most recently used.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with three resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_2160 = TemplateDatabase(SupportedResolution.R_2160)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_2160: db_2160,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with cache_size=2
        manager = TemplateManager(db_path, cache_size=2)

        # Load R_1080 and R_1440
        await manager.load_database(SupportedResolution.R_1080)
        await manager.load_database(SupportedResolution.R_1440)

        # Access R_1080 again (cache hit, should move to most recently used)
        with patch("logging.Logger.debug") as mock_log:
            await manager.load_database(SupportedResolution.R_1080)
            # Should log cache hit
            assert any("Cache hit" in str(call) for call in mock_log.call_args_list)

        # Load R_2160 - should evict R_1440 (LRU), not R_1080
        await manager.load_database(SupportedResolution.R_2160)
        assert len(TemplateManager._shared_databases) == 2
        assert (db_path, SupportedResolution.R_1080) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1440) not in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_2160) in TemplateManager._shared_databases


class TestGetAvailableResolutions:
    """Test suite for TemplateManager.get_available_resolutions method."""

    def test_get_available_resolutions_single(self, tmp_path: Path) -> None:
        """Test getting available resolutions with single resolution.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with one resolution
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        databases = {SupportedResolution.R_1080: db_1080}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        resolutions = manager.get_available_resolutions()

        assert len(resolutions) == 1
        assert SupportedResolution.R_1080 in resolutions

    def test_get_available_resolutions_multiple(self, tmp_path: Path) -> None:
        """Test getting available resolutions with multiple resolutions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with multiple resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        resolutions = manager.get_available_resolutions()

        assert len(resolutions) == 3
        assert SupportedResolution.R_1080 in resolutions
        assert SupportedResolution.R_1440 in resolutions
        assert SupportedResolution.R_720 in resolutions

    def test_get_available_resolutions_sorted(self, tmp_path: Path) -> None:
        """Test that available resolutions are sorted by value.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with resolutions in random order
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_720: db_720,
            SupportedResolution.R_1440: db_1440,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        resolutions = manager.get_available_resolutions()

        # Check that resolutions are sorted
        assert resolutions[0] == SupportedResolution.R_720
        assert resolutions[1] == SupportedResolution.R_1080
        assert resolutions[2] == SupportedResolution.R_1440

    def test_get_available_resolutions_missing_file(self, tmp_path: Path) -> None:
        """Test get_available_resolutions raises error when database file doesn't exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "nonexistent.h5"
        manager = TemplateManager(db_path)

        with pytest.raises(FileNotFoundError):
            manager.get_available_resolutions()

    def test_get_available_resolutions_corrupted_file(self, tmp_path: Path) -> None:
        """Test get_available_resolutions raises error for corrupted file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "corrupted.h5"
        db_path.write_text("corrupted data")

        manager = TemplateManager(db_path)

        with pytest.raises(ValueError):
            manager.get_available_resolutions()

    def test_get_available_resolutions_wrong_version(self, tmp_path: Path) -> None:
        """Test get_available_resolutions raises error for wrong database version.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "old_version.h5"

        # Create HDF5 with wrong version
        with h5py.File(str(db_path), "w") as f:
            f.attrs["version"] = 1  # Old version
            group = f.create_group("1080")
            group.attrs["resolution"] = "1080"
            group.attrs["template_count"] = 0
            group.attrs["icon_size"] = 0

        manager = TemplateManager(db_path)

        with pytest.raises(ValueError, match="version"):
            manager.get_available_resolutions()


class TestLoadAllResolutions:
    """Test suite for TemplateManager.load_all_resolutions method."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the shared cache before each test."""
        TemplateManager._shared_databases.clear()

    async def test_load_all_resolutions_single(self, tmp_path: Path) -> None:
        """Test loading all resolutions with single resolution.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with one resolution
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        databases = {SupportedResolution.R_1080: db_1080}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        all_dbs = await manager.load_all_resolutions()

        assert len(all_dbs) == 1
        assert SupportedResolution.R_1080 in all_dbs
        assert all_dbs[SupportedResolution.R_1080] is not None

    async def test_load_all_resolutions_multiple(self, tmp_path: Path) -> None:
        """Test loading all resolutions with multiple resolutions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with multiple resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        all_dbs = await manager.load_all_resolutions()

        assert len(all_dbs) == 3
        assert SupportedResolution.R_1080 in all_dbs
        assert SupportedResolution.R_1440 in all_dbs
        assert SupportedResolution.R_720 in all_dbs
        assert all_dbs[SupportedResolution.R_1080] is not None
        assert all_dbs[SupportedResolution.R_1440] is not None
        assert all_dbs[SupportedResolution.R_720] is not None

    async def test_load_all_resolutions_increases_cache_size(self, tmp_path: Path) -> None:
        """Test that load_all_resolutions increases cache size if too small.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with multiple resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with small cache size
        manager = TemplateManager(db_path, cache_size=1)
        assert manager.cache_size == 1

        # Load all resolutions
        await manager.load_all_resolutions()

        # Cache size should now be 3 (number of resolutions)
        assert manager.cache_size == 3

    async def test_load_all_resolutions_preserves_large_cache_size(self, tmp_path: Path) -> None:
        """Test that load_all_resolutions doesn't decrease cache size if already large.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with 3 resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create manager with cache size larger than number of resolutions
        manager = TemplateManager(db_path, cache_size=10)
        assert manager.cache_size == 10

        # Load all resolutions
        await manager.load_all_resolutions()

        # Cache size should remain 10 (not decreased to 3)
        assert manager.cache_size == 10

    async def test_load_all_resolutions_caches_all(self, tmp_path: Path) -> None:
        """Test that load_all_resolutions caches all loaded resolutions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with multiple resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_1440: db_1440,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.load_all_resolutions()

        # All resolutions should be in cache
        assert len(TemplateManager._shared_databases) == 3
        assert (db_path, SupportedResolution.R_1080) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_1440) in TemplateManager._shared_databases
        assert (db_path, SupportedResolution.R_720) in TemplateManager._shared_databases

    async def test_load_all_resolutions_with_templates(self, tmp_path: Path) -> None:
        """Test loading all resolutions with actual templates.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create databases with templates
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        template_1080 = IconTemplate(
            code="Item1080",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        db_1080.add_template(template_1080)

        db_720 = TemplateDatabase(SupportedResolution.R_720)
        template_720 = IconTemplate(
            code="Item720",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_720,
            image=np.zeros((24, 24, 3), dtype=np.uint8),
            phash=0,
        )
        db_720.add_template(template_720)

        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        all_dbs = await manager.load_all_resolutions()

        # Check that templates were loaded correctly
        assert len(all_dbs[SupportedResolution.R_1080].templates) == 1
        assert len(all_dbs[SupportedResolution.R_720].templates) == 1
        assert all_dbs[SupportedResolution.R_1080].templates[0].code == "Item1080"
        assert all_dbs[SupportedResolution.R_720].templates[0].code == "Item720"

    async def test_load_all_resolutions_missing_file(self, tmp_path: Path) -> None:
        """Test load_all_resolutions raises error when database file doesn't exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "nonexistent.h5"
        manager = TemplateManager(db_path)

        with pytest.raises(FileNotFoundError):
            await manager.load_all_resolutions()

    async def test_load_all_resolutions_corrupted_file(self, tmp_path: Path) -> None:
        """Test load_all_resolutions raises error for corrupted file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "corrupted.h5"
        db_path.write_text("corrupted data")

        manager = TemplateManager(db_path)

        with pytest.raises(ValueError):
            await manager.load_all_resolutions()


class TestPrepareDatabase:
    """Test suite for _prepare_resolution_data function."""

    def test_prepare_empty_database(self) -> None:
        """Test preparing an empty database returns minimal data."""
        from fs_tools.template_db.template_manager import _prepare_resolution_data

        empty_db = TemplateDatabase(SupportedResolution.R_1080)
        result = _prepare_resolution_data(SupportedResolution.R_1080, empty_db)

        assert result["template_count"] == 0
        assert result["icon_size"] == 0
        assert result["empty"] is True
        assert result["resolution"] == "1080"


class TestSaveDatabasesToHdf5:
    """Test suite for TemplateManager.save_databases_to_hdf5 static method."""

    def test_save_empty_databases_raises_error(self, tmp_path: Path) -> None:
        """Test that saving an empty databases dict raises ValueError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        output_path = tmp_path / "output.h5"

        with pytest.raises(ValueError) as exc_info:
            TemplateManager.save_databases_to_hdf5({}, output_path)

        assert "Cannot save empty databases dictionary" in str(exc_info.value)


class TestTemplateManagerEdgeCases:
    """Test suite for edge cases in TemplateManager."""

    def test_evict_to_size_handles_non_int_max_size(self) -> None:
        """Test that _evict_to_size handles non-int max_size gracefully."""
        from unittest.mock import MagicMock

        # Directly call the classmethod with a non-int value
        # Should not raise an exception - just return early
        TemplateManager._evict_to_size(MagicMock())

    def test_get_available_resolutions_with_invalid_key(self, tmp_path: Path) -> None:
        """Test get_available_resolutions skips invalid resolution keys.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        import h5py

        db_path = tmp_path / "test.h5"

        # Create database with valid and invalid resolution keys
        with h5py.File(str(db_path), "w") as f:
            # Valid resolution
            f.create_group("1080")
            # Invalid resolution key
            f.create_group("invalid_resolution")

        manager = TemplateManager(db_path)
        resolutions = manager.get_available_resolutions()

        # Should only contain the valid resolution
        assert len(resolutions) == 1
        assert SupportedResolution.R_1080 in resolutions


class TestSaveSingleResolution:
    """Test suite for TemplateManager.save_single_resolution static method."""

    def test_save_single_resolution_success(self, tmp_path: Path) -> None:
        """Test saving a single resolution to existing HDF5 file.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create initial database with one resolution
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        template = IconTemplate(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        db_1080.add_template(template)
        databases = {SupportedResolution.R_1080: db_1080}
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create a new database for 720p
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        template_720 = IconTemplate(
            code="TestItem720",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_720,
            image=np.zeros((24, 24, 3), dtype=np.uint8),
            phash=1,
        )
        db_720.add_template(template_720)

        # Save single resolution
        TemplateManager.save_single_resolution(
            database=db_720,
            resolution=SupportedResolution.R_720,
            output_path=db_path,
        )

        # Verify both resolutions exist
        manager = TemplateManager(db_path)
        resolutions = manager.get_available_resolutions()
        assert SupportedResolution.R_1080 in resolutions
        assert SupportedResolution.R_720 in resolutions

    def test_save_single_resolution_overwrites_existing(self, tmp_path: Path) -> None:
        """Test saving a resolution that already exists overwrites it.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create initial database
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        template1 = IconTemplate(
            code="OriginalItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        db_1080.add_template(template1)
        databases = {SupportedResolution.R_1080: db_1080}
        create_hdf5_database(db_path=db_path, databases=databases)

        # Create new database with different template
        db_1080_new = TemplateDatabase(SupportedResolution.R_1080)
        template2 = IconTemplate(
            code="NewItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.ones((32, 32, 3), dtype=np.uint8) * 128,
            phash=1,
        )
        db_1080_new.add_template(template2)

        # Save single resolution (overwrite)
        TemplateManager.save_single_resolution(
            database=db_1080_new,
            resolution=SupportedResolution.R_1080,
            output_path=db_path,
        )

        # Verify the new template is there
        with h5py.File(str(db_path), "r") as f:
            group = f["1080"]
            codes = group["codes"][:]  # type: ignore[index]
            assert b"NewItem" in codes  # type: ignore[operator]
            assert b"OriginalItem" not in codes  # type: ignore[operator]

    def test_save_single_resolution_missing_file_raises(self, tmp_path: Path) -> None:
        """Test saving to non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "nonexistent.h5"
        db = TemplateDatabase(SupportedResolution.R_1080)

        with pytest.raises(FileNotFoundError):
            TemplateManager.save_single_resolution(
                database=db,
                resolution=SupportedResolution.R_1080,
                output_path=db_path,
            )

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the shared cache before each test."""
        TemplateManager._shared_databases.clear()

    def test_save_single_resolution_invalidates_cache(self, tmp_path: Path) -> None:
        """Test that saving invalidates the cache for that resolution.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create initial database
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        template = IconTemplate(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        db_1080.add_template(template)
        databases = {SupportedResolution.R_1080: db_1080}
        create_hdf5_database(db_path=db_path, databases=databases)

        # Load into cache (instantiate to trigger cache population)
        _ = TemplateManager(db_path)
        cache_key = (db_path, SupportedResolution.R_1080)

        # Manually add to cache to simulate it being loaded
        TemplateManager._shared_databases[cache_key] = db_1080

        assert cache_key in TemplateManager._shared_databases

        # Save single resolution - should invalidate cache
        db_1080_new = TemplateDatabase(SupportedResolution.R_1080)
        TemplateManager.save_single_resolution(
            database=db_1080_new,
            resolution=SupportedResolution.R_1080,
            output_path=db_path,
        )

        # Cache should be invalidated
        assert cache_key not in TemplateManager._shared_databases
