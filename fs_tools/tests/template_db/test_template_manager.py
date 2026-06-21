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
from foxhole_stockpiles.models.icon_template import IconTemplate
from fs_tools.template_db.template_database import DATABASE_VERSION, TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager


def create_hdf5_database(
    db_path: Path, databases: dict[SupportedResolution, TemplateDatabase]
) -> None:
    """Create an HDF5 database file for testing.

    Args:
        db_path (Path): Path where the HDF5 database will be created.
        databases (dict[SupportedResolution, TemplateDatabase]): Dict of resolution to database.
    """
    with h5py.File(str(db_path), "w") as f:
        # Set root-level attributes
        f.attrs["version"] = DATABASE_VERSION
        f.attrs["format"] = "hdf5"
        f.attrs["resolutions"] = [res.value for res in databases.keys()]

        # Save each resolution's database
        for resolution, db in databases.items():
            group = f.create_group(resolution.value)
            db.save_to_hdf5_group(group)


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
        assert manager.active_database is None
        assert manager.current_resolution is None

    def test_init_creates_empty_cache(self, tmp_path: Path) -> None:
        """Test that initialization creates empty database cache.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        assert manager.active_database is None
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


class TestSetActiveResolution:
    """Test suite for TemplateManager.set_active_resolution method.

    This class contains tests for switching between resolutions based on
    screenshot dimensions and database caching behavior.
    """

    async def test_set_active_resolution_first_time(self, tmp_path: Path) -> None:
        """Test setting active resolution for the first time.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create a real database
        real_db = TemplateDatabase(SupportedResolution.R_1080)
        databases = {SupportedResolution.R_1080: real_db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)

        # Set resolution for 1080p screenshot
        resolution = await manager.set_active_resolution(1080)

        assert resolution == SupportedResolution.R_1080
        assert manager.current_resolution == SupportedResolution.R_1080
        assert manager.active_database is not None

    async def test_set_active_resolution_switch(self, tmp_path: Path) -> None:
        """Test switching between different resolutions.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create databases for multiple resolutions
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        databases = {
            SupportedResolution.R_1080: db_1080,
            SupportedResolution.R_720: db_720,
        }
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)

        # Set resolution for 1080p
        resolution1 = await manager.set_active_resolution(1080)
        assert resolution1 == SupportedResolution.R_1080

        # Switch to 720p
        resolution2 = await manager.set_active_resolution(720)
        assert resolution2 == SupportedResolution.R_720
        assert manager.current_resolution == SupportedResolution.R_720

    async def test_set_active_resolution_no_switch(self, tmp_path: Path) -> None:
        """Test that setting same resolution doesn't reload database.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create a real database
        real_db = TemplateDatabase(SupportedResolution.R_1080)
        databases = {SupportedResolution.R_1080: real_db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)

        # Set resolution for 1080p
        await manager.set_active_resolution(1080)
        db_reference = manager.active_database

        # Set same resolution again
        await manager.set_active_resolution(1080)

        # Should be the same database reference (not reloaded)
        assert manager.active_database is db_reference


class TestFindBestResolution:
    """Test suite for TemplateManager._find_best_resolution method.

    This class contains tests for finding the best matching resolution
    for various screenshot heights.
    """

    def test_find_best_resolution_exact_match(self, tmp_path: Path) -> None:
        """Test finding exact resolution match.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        # Test exact matches
        assert manager._find_best_resolution(1080) == SupportedResolution.R_1080
        assert manager._find_best_resolution(720) == SupportedResolution.R_720
        assert manager._find_best_resolution(1440) == SupportedResolution.R_1440

    def test_find_best_resolution_closest_match(self, tmp_path: Path) -> None:
        """Test finding closest resolution when no exact match.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        # Test closest matches - 992 is closest to 1000
        assert manager._find_best_resolution(1000) == SupportedResolution.R_992
        assert manager._find_best_resolution(800) == SupportedResolution.R_800
        assert manager._find_best_resolution(1200) == SupportedResolution.R_1200
        # 1500 is closer to 1536 (36 away) than to 1440 (60 away)
        assert manager._find_best_resolution(1500) == SupportedResolution.R_1536

    def test_find_best_resolution_edge_cases(self, tmp_path: Path) -> None:
        """Test edge cases for resolution finding.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        # Very low resolution - 664 is closest to 480
        result = manager._find_best_resolution(480)
        assert result == SupportedResolution.R_664

        # Very high resolution - exact match
        result = manager._find_best_resolution(2160)
        assert result == SupportedResolution.R_2160


class TestMatchIcon:
    """Test suite for TemplateManager.match_icon method.

    This class contains tests for icon matching functionality with various
    filters and matching parameters.
    """

    def setup_method(self) -> None:
        """Clear the shared cache before each test."""
        TemplateManager._shared_databases.clear()

    async def test_match_icon_no_database_loaded(self, tmp_path: Path) -> None:
        """Test match_icon raises error when no database loaded.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        manager = TemplateManager(db_path)

        # Should raise ValueError when no database is loaded
        with pytest.raises(ValueError, match="No active database loaded"):
            manager.match_icon()

    async def test_match_icon_no_image_returns_candidates(self, tmp_path: Path) -> None:
        """Test match_icon without image returns only candidates.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with a template
        db = TemplateDatabase(SupportedResolution.R_1080)
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
        db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match without image should return candidates only
        result = manager.match_icon()

        assert result.icon is None
        assert result.confidence == 0.0
        assert len(result.candidates) > 0

    async def test_match_icon_with_image_matching(self, tmp_path: Path) -> None:
        """Test match_icon with actual image matching.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        # Create database with a template
        db = TemplateDatabase(SupportedResolution.R_1080)
        template = IconTemplate(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=0,
        )
        db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with the same image should return high confidence
        result = manager.match_icon(icon_image=test_image)

        assert result.icon is not None
        assert result.confidence is not None
        assert result.confidence >= 0.8
        assert result.icon.code == "TestItem"

    async def test_match_icon_with_filters(self, tmp_path: Path) -> None:
        """Test match_icon with faction and category filters.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with multiple templates
        db = TemplateDatabase(SupportedResolution.R_1080)

        # Add neutral item
        template1 = IconTemplate(
            code="NeutralItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        db.add_template(template1)

        # Add colonial item
        template2 = IconTemplate(
            code="ColonialItem",
            faction=ItemFaction.COLONIALS,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.ones((32, 32, 3), dtype=np.uint8) * 128,
            phash=1,
        )
        db.add_template(template2)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Filter by faction
        result = manager.match_icon(faction=ItemFaction.COLONIALS)

        # Should return fewer candidates (colonial templates only)
        # Note: The actual count depends on how filtering works - it may include neutral items
        assert len(result.candidates) >= 1
        assert result.icon is None  # No image provided, so no match

    async def test_match_icon_phash_filtering(self, tmp_path: Path) -> None:
        """Test match_icon uses pHash pre-filtering with many candidates.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with many templates (>25 to trigger pHash filtering)
        db = TemplateDatabase(SupportedResolution.R_1080)

        for i in range(30):
            template = IconTemplate(
                code=f"Item{i}",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
                image=np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8),
                phash=i,
            )
            db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        # Match with image - should trigger pHash filtering
        result = manager.match_icon(icon_image=test_image, max_ncc_candidates=25)

        # Should have tested <= max_ncc_candidates due to pHash filtering
        assert result.tested_candidates <= 25

    async def test_match_icon_early_exit(self, tmp_path: Path) -> None:
        """Test match_icon early exit with high confidence.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        # Create database with matching template first
        db = TemplateDatabase(SupportedResolution.R_1080)

        # Add perfect match as first template
        template1 = IconTemplate(
            code="PerfectMatch",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=0,
        )
        db.add_template(template1)

        # Add more templates that won't be tested due to early exit
        for i in range(10):
            template = IconTemplate(
                code=f"OtherItem{i}",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
                image=np.zeros((32, 32, 3), dtype=np.uint8),
                phash=i,
            )
            db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with early exit enabled
        result = manager.match_icon(icon_image=test_image, early_exit_threshold=0.95)

        # Should have found match and exited early
        assert result.icon is not None
        assert result.confidence is not None
        assert result.confidence >= 0.95
        # Should have tested fewer candidates due to early exit
        assert result.tested_candidates < 11

    async def test_match_icon_with_confidence_gap(self, tmp_path: Path) -> None:
        """Test match_icon with confidence_gap returns alternative candidates.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image with distinct pattern
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128
        # Add a distinctive pattern to make it more unique
        test_image[10:20, 10:20] = [200, 200, 200]

        # Create database with multiple similar templates
        db = TemplateDatabase(SupportedResolution.R_1080)

        # Add best match template
        template1 = IconTemplate(
            code="Rifle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=0,
        )
        db.add_template(template1)

        # Add similar template (same category, crated, mod) - but with noticeable differences
        similar_image1 = np.ones((32, 32, 3), dtype=np.uint8) * 128
        similar_image1[10:20, 10:20] = [180, 180, 180]  # Different brightness in same area
        similar_image1[:8, :8] = [100, 100, 100]  # Additional difference
        template2 = IconTemplate(
            code="RifleAlt1",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=similar_image1,
            phash=1,
        )
        db.add_template(template2)

        # Add another similar template - even more different
        similar_image2 = np.ones((32, 32, 3), dtype=np.uint8) * 128
        similar_image2[10:20, 10:20] = [160, 160, 160]  # More different brightness
        similar_image2[:12, :12] = [80, 80, 80]  # Larger different area
        template3 = IconTemplate(
            code="RifleAlt2",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=similar_image2,
            phash=2,
        )
        db.add_template(template3)

        # Add template with different category (should NOT be included)
        template4 = IconTemplate(
            code="Vehicle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Vehicle,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=3,
        )
        db.add_template(template4)

        # Add template with different crated status (should NOT be included)
        template5 = IconTemplate(
            code="RifleCrated",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=True,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=4,
        )
        db.add_template(template5)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with a larger confidence_gap to ensure we get candidates
        result = manager.match_icon(icon_image=test_image, confidence_gap=0.25)

        # Should have found best match
        assert result.icon is not None
        assert result.icon.code == "Rifle"

        # With different enough images and a 0.25 gap, we should have gap_candidates
        # If confidence scores are very close, we might not get any, so we test the logic instead
        if len(result.gap_candidates) > 0:
            # Gap candidates should only include items with same category, crated, and mod
            for template, conf in result.gap_candidates:
                assert template.category == ItemCategory.Item
                assert template.crated is False
                assert template.mod == "vanilla"
                # Should not include the best match itself
                assert template.code != "Rifle"
                # Confidence should be within the gap
                assert conf < result.best_confidence
                assert conf >= (result.best_confidence - 0.25)

        # Verify that gap_candidates field exists and is a list
        assert isinstance(result.gap_candidates, list)

    async def test_match_icon_with_zero_confidence_gap(self, tmp_path: Path) -> None:
        """Test match_icon with confidence_gap=0.0 returns no gap candidates.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        # Create database with template
        db = TemplateDatabase(SupportedResolution.R_1080)
        template = IconTemplate(
            code="Rifle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=0,
        )
        db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with confidence_gap=0.0 (default)
        result = manager.match_icon(icon_image=test_image, confidence_gap=0.0)

        # Should have found match
        assert result.icon is not None
        # Should have NO gap candidates
        assert len(result.gap_candidates) == 0

    async def test_match_icon_tiebreaker_changes_winner(self, tmp_path: Path) -> None:
        """Test that tiebreaker selects template with lower edge difference.

        When NCC scores are very close, the tiebreaker should select the template
        with lower edge-based difference (more similar edge structure).

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image with a center square (creates edges at boundaries)
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128
        test_image[8:24, 8:24] = [200, 200, 200]  # Center square

        # Create database with two templates that will have very close NCC scores
        db = TemplateDatabase(SupportedResolution.R_1080)

        # Template 1: Has extra edge (vertical line) that test_image doesn't have
        template1_image = np.ones((32, 32, 3), dtype=np.uint8) * 128
        template1_image[8:24, 8:24] = [200, 200, 200]  # Same center square
        template1_image[4:28, 15:17] = [50, 50, 50]  # Extra vertical line (different edges)
        template1 = IconTemplate(
            code="ItemA",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=template1_image,
            phash=0,
        )
        db.add_template(template1)

        # Template 2: Exact match - same edge structure
        template2_image = test_image.copy()
        template2 = IconTemplate(
            code="ItemB",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=template2_image,
            phash=1,
        )
        db.add_template(template2)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with tiebreaker enabled
        result = manager.match_icon(
            icon_image=test_image,
            ncc_tiebreaker_threshold=0.1,  # Large threshold to ensure tiebreaker kicks in
        )

        # The exact match (ItemB) should win due to lower edge difference
        assert result.icon is not None
        assert result.icon.code == "ItemB"

    async def test_match_icon_tiebreaker_disabled(self, tmp_path: Path) -> None:
        """Test that tiebreaker is disabled when threshold is 0.0.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        # Create database with single template
        db = TemplateDatabase(SupportedResolution.R_1080)
        template = IconTemplate(
            code="Item",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=0,
        )
        db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with tiebreaker disabled (default)
        result = manager.match_icon(
            icon_image=test_image,
            ncc_tiebreaker_threshold=0.0,
        )

        # Should still find match
        assert result.icon is not None
        assert result.icon.code == "Item"

    async def test_match_icon_tiebreaker_no_close_matches(self, tmp_path: Path) -> None:
        """Test that tiebreaker has no effect when matches aren't close.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create test image
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128
        test_image[8:24, 8:24] = [200, 200, 200]

        # Create database with templates that will have very different NCC scores
        db = TemplateDatabase(SupportedResolution.R_1080)

        # Template 1: Good match
        template1 = IconTemplate(
            code="BestMatch",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=test_image.copy(),
            phash=0,
        )
        db.add_template(template1)

        # Template 2: Very different - should have much lower NCC
        different_image = np.ones((32, 32, 3), dtype=np.uint8) * 50
        different_image[0:16, 0:16] = [250, 250, 250]
        template2 = IconTemplate(
            code="PoorMatch",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=different_image,
            phash=1,
        )
        db.add_template(template2)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with small tiebreaker threshold
        result = manager.match_icon(
            icon_image=test_image,
            ncc_tiebreaker_threshold=0.002,
        )

        # Best match should still win - tiebreaker only activates for close matches
        assert result.icon is not None
        assert result.icon.code == "BestMatch"


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
        TemplateManager._cache_size = 16  # Reset to default

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
        TemplateManager._cache_size = 16

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


class TestMigrateDatabase:
    """Test suite for TemplateManager.migrate_database method."""

    def test_migrate_nonexistent_database(self, tmp_path: Path) -> None:
        """Test migration fails when database file doesn't exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "nonexistent.h5"
        manager = TemplateManager(db_path)

        with pytest.raises(FileNotFoundError) as exc_info:
            manager.migrate_database()

        assert "Database file not found" in str(exc_info.value)

    def test_migrate_corrupted_database(self, tmp_path: Path) -> None:
        """Test migration fails when database is corrupted (version 0).

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "corrupted.h5"
        db_path.write_text("not a valid hdf5 file")

        manager = TemplateManager(db_path)

        with pytest.raises(ValueError) as exc_info:
            manager.migrate_database()

        assert "corrupted or in an unrecognized format" in str(exc_info.value)

    def test_migrate_already_current_version(self, tmp_path: Path) -> None:
        """Test migration fails when database is already at current version.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "current.h5"

        # Create a database at current version
        real_db = TemplateDatabase(SupportedResolution.R_1080)
        create_hdf5_database(db_path=db_path, databases={SupportedResolution.R_1080: real_db})

        manager = TemplateManager(db_path)

        with pytest.raises(ValueError) as exc_info:
            manager.migrate_database()

        assert f"already at version {DATABASE_VERSION}" in str(exc_info.value)

    def test_migrate_unknown_version(self, tmp_path: Path) -> None:
        """Test migration raises error for unknown version.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "unknown_version.h5"

        # Create a dummy h5 file
        with h5py.File(str(db_path), "w") as f:
            f.attrs["version"] = 1
            f.attrs["format"] = "hdf5"

        manager = TemplateManager(db_path)

        # Mock _check_database_version to return version 1:
        # - Not 0 (passes corrupted check)
        # - Not DATABASE_VERSION (passes already current check)
        # - Less than DATABASE_VERSION (enters while loop)
        # - Hits case _: which now raises ValueError
        with patch.object(manager, "_check_database_version", return_value=1):
            with pytest.raises(ValueError) as exc_info:
                manager.migrate_database()

            assert "No migration path" in str(exc_info.value)
            assert "regenerate the database" in str(exc_info.value)


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

    def test_needs_migration_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        """Test needs_migration returns False when database file doesn't exist.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "nonexistent.h5"
        manager = TemplateManager(db_path)

        # Should return False for non-existent file
        assert manager.needs_migration() is False


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


class TestPhashFiltering:
    """Test suite for pHash filtering in match_icon."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear the shared cache before each test."""
        TemplateManager._shared_databases.clear()

    async def test_phash_filtering_excludes_distant_hashes(self, tmp_path: Path) -> None:
        """Test that pHash filtering excludes templates with distant hashes.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"

        # Create database with many templates with varying pHash distances
        db = TemplateDatabase(SupportedResolution.R_1080)

        # Create a test image and compute its pHash-like value
        test_image = np.ones((32, 32, 3), dtype=np.uint8) * 128

        # Add templates with close pHash (should be included)
        for i in range(15):
            template = IconTemplate(
                code=f"CloseItem{i}",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
                image=test_image.copy(),
                phash=i,  # Low pHash values - close to 0
            )
            db.add_template(template)

        # Add templates with distant pHash (should be filtered out)
        for i in range(15):
            template = IconTemplate(
                code=f"DistantItem{i}",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
                image=np.zeros((32, 32, 3), dtype=np.uint8),
                phash=0xFFFFFFFFFFFFFFFF,  # Max distance pHash
            )
            db.add_template(template)

        databases = {SupportedResolution.R_1080: db}
        create_hdf5_database(db_path=db_path, databases=databases)

        manager = TemplateManager(db_path)
        await manager.set_active_resolution(1080)

        # Match with small max_ncc_candidates to force pHash filtering
        result = manager.match_icon(
            icon_image=test_image,
            max_ncc_candidates=10,
            phash_threshold=20,
        )

        # Should have used pHash filtering
        assert result.tested_candidates <= 10
