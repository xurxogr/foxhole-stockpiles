"""Tests for PakCoverageWorker and the coverage status rules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fs_assets.types import PakCoverage

from fs_tools.gui.utils.pak_coverage_status import (
    covers_all_overlays,
    has_catalog_icons,
    missing_overlays,
)
from fs_tools.gui.utils.pak_coverage_worker import PakCoverageWorker

_PAK_COVERAGE = "fs_tools.gui.utils.pak_coverage_worker.fs_assets.pak_coverage"


def coverage(
    main_icons_found: int = 10,
    overlays_found: int = 4,
    has_crate_icon: bool = True,
) -> PakCoverage:
    """Build a coverage report over a catalog with 10 main icons and 4 overlays.

    Args:
        main_icons_found (int): Main icons found. Defaults to 10.
        overlays_found (int): Overlays found (crate icon included). Defaults to 4.
        has_crate_icon (bool): Whether the crate icon was found. Defaults to True.

    Returns:
        PakCoverage: The coverage report.
    """
    return {
        "main_icons_found": main_icons_found,
        "main_icons_total": 10,
        "overlays_found": overlays_found,
        "overlays_total": 4,
        "has_crate_icon": has_crate_icon,
    }


def test_run_reports_the_coverage_of_every_pak(tmp_path: Path) -> None:
    """run() checks all the paks against the catalog and emits the report."""
    worker = PakCoverageWorker(catalog_path=tmp_path / "catalog.json", pak_files=["a.pak", "b.pak"])
    ready, failed = MagicMock(), MagicMock()
    worker.coverage_ready.connect(ready)
    worker.failed.connect(failed)

    with patch(_PAK_COVERAGE, return_value=coverage()) as pak_coverage:
        worker.run()

    pak_coverage.assert_called_once_with(
        catalog=str(tmp_path / "catalog.json"), pak=["a.pak", "b.pak"]
    )
    ready.assert_called_once_with(coverage())
    failed.assert_not_called()


def test_run_reports_failures(tmp_path: Path) -> None:
    """A failing check is reported through the failed signal."""
    worker = PakCoverageWorker(catalog_path=tmp_path / "catalog.json", pak_files=["a.pak"])
    ready, failed = MagicMock(), MagicMock()
    worker.coverage_ready.connect(ready)
    worker.failed.connect(failed)

    with patch(_PAK_COVERAGE, side_effect=RuntimeError("not a pak")):
        worker.run()

    failed.assert_called_once_with("not a pak")
    ready.assert_not_called()


def test_has_catalog_icons() -> None:
    """A pak set is usable only if it has at least one catalog main icon."""
    assert has_catalog_icons(coverage(main_icons_found=1)) is True
    assert has_catalog_icons(coverage(main_icons_found=0)) is False


def test_covers_all_overlays() -> None:
    """Every subtype icon and the crate icon must be present."""
    assert covers_all_overlays(coverage()) is True
    assert covers_all_overlays(coverage(overlays_found=3)) is False


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (coverage(), []),
        (coverage(overlays_found=3, has_crate_icon=False), ["crate icon"]),
        (coverage(overlays_found=1), ["subicons"]),
        (coverage(overlays_found=0, has_crate_icon=False), ["crate icon", "subicons"]),
    ],
)
def test_missing_overlays(report: PakCoverage, expected: list[str]) -> None:
    """The missing overlays are named so the user knows what is lacking."""
    assert missing_overlays(report) == expected
