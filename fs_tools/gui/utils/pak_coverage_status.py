"""Rules that turn an ``fs_assets.pak_coverage`` report into an import decision."""

from fs_assets.types import PakCoverage


def has_catalog_icons(coverage: PakCoverage) -> bool:
    """Return whether the paks contain at least one of the catalog's main icons.

    Args:
        coverage (PakCoverage): The coverage report of the mod paks.

    Returns:
        bool: True if the paks can be imported as a mod.
    """
    return coverage["main_icons_found"] > 0


def covers_all_overlays(coverage: PakCoverage) -> bool:
    """Return whether the paks contain every subtype icon and the crate icon.

    A mod lacking some of them needs the base game's PAK as a fallback, and that
    PAK is only valid if it covers them all.

    Args:
        coverage (PakCoverage): The coverage report.

    Returns:
        bool: True if no overlay is missing.
    """
    return coverage["overlays_found"] == coverage["overlays_total"]


def missing_overlays(coverage: PakCoverage) -> list[str]:
    """Name the kinds of overlay the paks lack.

    Args:
        coverage (PakCoverage): The coverage report.

    Returns:
        list[str]: ``"crate icon"`` and/or ``"subicons"``; empty when complete.
    """
    crate_found = 1 if coverage["has_crate_icon"] else 0
    # The overlay totals count the crate icon once; the rest are subtype icons.
    subicons_found = coverage["overlays_found"] - crate_found
    subicons_total = coverage["overlays_total"] - 1

    missing = []
    if not coverage["has_crate_icon"]:
        missing.append("crate icon")
    if subicons_found < subicons_total:
        missing.append("subicons")
    return missing
