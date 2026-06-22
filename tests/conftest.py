"""Pytest configuration and shared fixtures.

This module provides pytest configuration and shared fixtures for the Foxhole Stockpiles
test suite. It includes fixtures for temporary directories, sample data, mock objects,
and test environment setup.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings


@pytest.fixture(autouse=True)
def isolate_app_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Generator[None, None, None]:
    """Isolate AppSettings from the developer's machine for every test.

    By default ``AppSettings`` loads ``~/.fs_config`` and any ``FS_*``-prefixed
    environment variables, so an unguarded test would pick up whatever
    configuration happens to exist on the machine. That makes the suite pass or
    fail depending on the developer's real config and diverge from CI (where no
    config file exists). This autouse fixture pins every test to a clean,
    default ``AppSettings``:

    - The JSON config source is pointed at a path that does not exist, so it
      yields an empty dict and the model's field defaults apply.
    - All ``FS_*`` environment variables are removed.
    - The ``get_settings`` LRU cache is cleared before and after the test so no
      real-config instance leaks in or out.

    Tests that need specific configuration must supply it themselves, either by
    passing values to ``AppSettings(...)`` or by writing a config file and
    pointing ``json_file`` at it.

    Yields:
        None: Control to the test while the isolation is active.
    """
    for key in list(os.environ):
        if key.startswith("FS_"):
            monkeypatch.delenv(key, raising=False)

    # A path under the per-test tmp dir that we deliberately never create, so the
    # JSON settings source treats it as absent and falls back to defaults.
    absent_config = tmp_path / "absent_fs_config.json"
    monkeypatch.setitem(AppSettings.model_config, "json_file", str(absent_config))

    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


# Configure Qt to run in offscreen mode for all tests to prevent GUI windows from appearing
# This is essential for CI/CD environments and automated testing
def pytest_configure(config: Any) -> None:
    """Configure pytest to run Qt tests in offscreen mode.

    Args:
        config: Pytest configuration object
    """
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing.

    Yields:
        Path: A Path object pointing to a temporary directory that will be
            automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_catalog_data() -> list[dict[str, Any]]:
    """Provide sample catalog data for testing.

    Returns:
        list[dict[str, Any]]: A list of dictionaries containing sample catalog item data
            with fields like CodeName, Faction, Category, IconPath, and SubiconPath.
    """
    return [
        {
            "CodeName": "Rifle",
            "Faction": "neutral",
            "Category": "weapon",
            "IconPath": "icons/rifle.png",
            "SubiconPath": "",
        },
        {
            "CodeName": "ColonialRifle",
            "Faction": "Colonials",
            "Category": "weapon",
            "IconPath": "icons/colonial_rifle.png",
            "SubiconPath": "icons/colonial_rifle_sub.png",
        },
        {
            "CodeName": "WardenTank",
            "Faction": "Wardens",
            "Category": "vehicle",
            "IconPath": "icons/warden_tank.png",
            "SubiconPath": "",
        },
        {
            "CodeName": "SupplyCrate",
            "Faction": "neutral",
            "Category": "item",
            "IconPath": "icons/supply_crate.png",
            "SubiconPath": "icons/supply_crate_sub.png",
        },
    ]


@pytest.fixture
def mock_image_array() -> np.ndarray[Any, np.dtype[np.uint8]]:
    """Create a mock numpy array representing a grayscale image.

    Returns:
        np.ndarray[Any, np.dtype[np.uint8]]: A 64x64 grayscale image array with
            some test patterns for non-uniform pixel values.
    """
    # Create a simple 64x64 grayscale image
    image = np.zeros((64, 64), dtype=np.uint8)
    # Add some pattern to make it non-uniform
    image[16:48, 16:48] = 128
    image[24:40, 24:40] = 255
    return image


@pytest.fixture
def mock_color_image_array() -> np.ndarray[Any, np.dtype[np.uint8]]:
    """Create a mock numpy array representing a color image.

    Returns:
        np.ndarray[Any, np.dtype[np.uint8]]: A 64x64x3 BGR color image array with
            colored test patterns including orange and green squares.
    """
    # Create a simple 64x64 BGR image
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    # Add some color patterns
    image[16:48, 16:48] = [255, 128, 0]  # Orange square
    image[24:40, 24:40] = [0, 255, 0]  # Green square
    return image


@pytest.fixture(autouse=True)
def reset_logging() -> Generator[None, None, None]:
    """Reset logging configuration after each test.

    This fixture automatically runs after each test to clean up logging handlers
    and prevent interference between tests.

    Yields:
        None: This fixture yields control back to the test and then performs cleanup.
    """
    import logging

    yield

    # Clear all handlers to prevent interference between tests
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


@pytest.fixture
def mock_pak_file(temp_dir: Path) -> Path:
    """Create a mock PAK file for testing.

    Args:
        temp_dir (Path): Temporary directory path from the temp_dir fixture.

    Returns:
        Path: Path to the created mock PAK file with dummy content.
    """
    pak_path = temp_dir / "test.pak"
    # Create a dummy file with some content
    pak_path.write_bytes(b"PAK\x00" + b"\x00" * 100)
    return pak_path


@pytest.fixture
def mock_catalog_file(temp_dir: Path, sample_catalog_data: list[dict[str, Any]]) -> Path:
    """Create a mock catalog.json file for testing.

    Args:
        temp_dir (Path): Temporary directory path from the temp_dir fixture.
        sample_catalog_data (list[dict[str, Any]]): Sample catalog data from the
            sample_catalog_data fixture.

    Returns:
        Path: Path to the created mock catalog.json file containing the sample data.
    """
    import json

    catalog_path = temp_dir / "catalog.json"
    with open(catalog_path, "w") as f:
        json.dump(sample_catalog_data, f)

    return catalog_path
