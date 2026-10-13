"""Tests for the template store backed by fs-assets (real databases, no mocks)."""

from pathlib import Path

import fs_assets
import pytest
from PIL import Image

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.core.template_store import (
    delete_icon,
    read_all_resolutions,
    read_resolution,
    read_statistics,
    replace_icon,
)


def _png(path: Path, color: tuple[int, int, int]) -> Path:
    """Write a solid-color opaque 64x64 PNG.

    Args:
        path (Path): Where to write it.
        color (tuple[int, int, int]): The RGB color.

    Returns:
        Path: The written path.
    """
    Image.new("RGB", (64, 64), color).save(path)
    return path


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """Create a database with a Warden rifle at 1080p and 1440p and a crated pistol at 1080p.

    Args:
        tmp_path (Path): Temporary directory path.

    Returns:
        Path: The database path.
    """
    db = tmp_path / "templates.h5"
    rifle = _png(tmp_path / "rifle.png", (200, 100, 50))
    fs_assets.modify_icon(
        str(db),
        code="RifleW",
        faction="wardens",
        category="item",
        icon=str(rifle),
        resolution=[1080, 1440],
    )
    fs_assets.modify_icon(
        str(db),
        code="Pistol",
        faction="neutral",
        category="item",
        crated=True,
        mod_name="clean",
        icon=str(rifle),
        resolution=[1080],
    )
    return db


def test_read_resolution_returns_icon_templates(database: Path) -> None:
    """Templates come back with their metadata and a BGR image of the right size."""
    templates = read_resolution(database, SupportedResolution("1080"))

    rifle = next(template for template in templates if template.code == "RifleW")
    assert rifle.faction == ItemFaction.WARDENS
    assert rifle.category == ItemCategory.Item
    assert rifle.crated is False
    assert rifle.mod == "vanilla"
    assert rifle.resolution == SupportedResolution("1080")
    assert rifle.image.shape == (32, 32, 3)
    assert rifle.image[0, 0].tolist() == [50, 100, 200]
    expected_phash = fs_assets.read_templates(str(database), 1080)[0]["phash"]
    assert rifle.phash == expected_phash


def test_read_all_resolutions_skips_empty_ones(database: Path) -> None:
    """Only resolutions holding templates are returned."""
    all_templates = read_all_resolutions(database)

    assert sorted(int(resolution.value) for resolution in all_templates) == [1080, 1440]
    assert len(all_templates[SupportedResolution("1080")]) == 2
    assert len(all_templates[SupportedResolution("1440")]) == 1


def test_read_statistics_counts_per_mod_and_resolution(database: Path) -> None:
    """Statistics list the resolutions with templates and the count per mod."""
    stats = read_statistics(database)

    assert stats.resolutions == ["1080", "1440"]
    assert stats.mod_stats == {"vanilla": {"1080": 1, "1440": 1}, "clean": {"1080": 1}}


def test_replace_icon_changes_only_that_resolution(database: Path, tmp_path: Path) -> None:
    """Replacing an icon rewrites its template at one resolution only."""
    rifle = read_resolution(database, SupportedResolution("1080"))[0]
    blue = _png(tmp_path / "blue.png", (0, 0, 255))

    replace_icon(database, rifle, blue)

    at_1080 = read_resolution(database, SupportedResolution("1080"))
    at_1440 = read_resolution(database, SupportedResolution("1440"))
    replaced = next(template for template in at_1080 if template.code == "RifleW")
    assert replaced.image[0, 0].tolist() == [255, 0, 0]
    assert at_1440[0].image[0, 0].tolist() == [50, 100, 200]


def test_delete_icon_removes_only_that_template(database: Path) -> None:
    """Deleting removes the matching template at its resolution only."""
    pistol = next(
        template
        for template in read_resolution(database, SupportedResolution("1080"))
        if template.code == "Pistol"
    )

    delete_icon(database, pistol)

    codes = [template.code for template in read_resolution(database, SupportedResolution("1080"))]
    assert codes == ["RifleW"]
    assert len(read_resolution(database, SupportedResolution("1440"))) == 1
