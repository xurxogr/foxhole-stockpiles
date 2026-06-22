"""Tests for TemplateManager database statistics functionality."""

from pathlib import Path

import pytest

from fs_tools.models.database_statistics import DatabaseStatistics
from fs_tools.template_db.template_manager import TemplateManager


@pytest.fixture
def hdf5_database_path() -> Path:
    """Get path to test HDF5 database.

    Returns:
        Path: Path to test HDF5 database file
    """
    return Path(__file__).parent.parent / "fixtures" / "test_db_v1.h5"


@pytest.fixture
def template_manager(hdf5_database_path: Path) -> TemplateManager:
    """Create a TemplateManager instance with a valid HDF5 database.

    Args:
        hdf5_database_path (Path): Path to a valid test HDF5 database

    Returns:
        TemplateManager: Configured template manager instance
    """
    return TemplateManager(database_path=hdf5_database_path)


def test_get_database_statistics_returns_correct_model(template_manager: TemplateManager) -> None:
    """Test that get_database_statistics returns a DatabaseStatistics model.

    Args:
        template_manager (TemplateManager): Template manager instance
    """
    stats = template_manager.get_database_statistics()

    assert isinstance(stats, DatabaseStatistics)
    assert isinstance(stats.resolutions, list)
    assert isinstance(stats.mod_stats, dict)


def test_get_database_statistics_has_resolutions(template_manager: TemplateManager) -> None:
    """Test that statistics include resolution information.

    Args:
        template_manager (TemplateManager): Template manager instance
    """
    stats = template_manager.get_database_statistics()

    assert len(stats.resolutions) > 0
    # Resolutions should be strings representing pixel heights
    for res in stats.resolutions:
        assert isinstance(res, str)
        assert res.isdigit()


def test_get_database_statistics_has_mod_stats(template_manager: TemplateManager) -> None:
    """Test that statistics include mod-level information.

    Args:
        template_manager (TemplateManager): Template manager instance
    """
    stats = template_manager.get_database_statistics()

    assert len(stats.mod_stats) > 0
    # Each mod should have resolution -> count mapping
    for mod_name, res_counts in stats.mod_stats.items():
        assert isinstance(mod_name, str)
        assert isinstance(res_counts, dict)
        # Each resolution should have a count
        for res, count in res_counts.items():
            assert isinstance(res, str)
            assert isinstance(count, int)
            assert count > 0


def test_get_database_statistics_mod_counts_per_resolution(
    template_manager: TemplateManager,
) -> None:
    """Test that each mod has counts for each resolution.

    Args:
        template_manager (TemplateManager): Template manager instance
    """
    stats = template_manager.get_database_statistics()

    # Each mod should potentially have entries for available resolutions
    for _mod_name, res_counts in stats.mod_stats.items():
        # Counts should be positive integers
        for count in res_counts.values():
            assert count > 0


def test_get_database_statistics_nonexistent_database() -> None:
    """Test that statistics fail gracefully for nonexistent database."""
    manager = TemplateManager(database_path=Path("/nonexistent/database.h5"))

    with pytest.raises(FileNotFoundError):
        manager.get_database_statistics()


def test_get_database_statistics_sorted_mods(template_manager: TemplateManager) -> None:
    """Test that mod names are sorted alphabetically.

    Args:
        template_manager (TemplateManager): Template manager instance
    """
    stats = template_manager.get_database_statistics()

    mod_names = list(stats.mod_stats.keys())
    assert mod_names == sorted(mod_names)


def test_get_database_statistics_resolutions_sorted(template_manager: TemplateManager) -> None:
    """Test that resolutions are sorted by numeric value.

    Args:
        template_manager (TemplateManager): Template manager instance
    """
    stats = template_manager.get_database_statistics()

    # Convert to integers and verify sorting
    res_ints = [int(r) for r in stats.resolutions]
    assert res_ints == sorted(res_ints)
