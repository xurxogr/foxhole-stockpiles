"""Utility functions for the stockpile system."""

import sys
from pathlib import Path

import fs_sav


def is_frozen() -> bool:
    """Check if running as a PyInstaller frozen executable.

    Returns:
        bool: True if running as frozen executable, False otherwise
    """
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundled_resource_path(relative_path: str) -> Path:
    """Get the path to a bundled resource, handling both dev and PyInstaller modes.

    When running as a PyInstaller bundle, resources are extracted to a temporary
    directory (sys._MEIPASS). This function resolves the correct path for both
    development mode (relative to current directory) and frozen mode.

    Args:
        relative_path (str): Path relative to project root (e.g., "tessdata").

    Returns:
        Path: Absolute path to the resource

    Example:
        >>> tessdata_path = get_bundled_resource_path("tessdata")
    """
    if is_frozen():
        # Running as PyInstaller bundle - use _MEIPASS
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # Development mode - use current working directory
        base_path = Path.cwd()

    return base_path / relative_path


# ==================== Savefile Locator Utilities ====================


def find_mapdata_file(save_dir: Path) -> Path | None:
    """Find the most recent MapData.sav file in a save directory.

    Several Steam accounts can leave one <SteamID64>_MapData.sav each in
    the same folder; the most recently written one is picked.

    Args:
        save_dir (Path): Save games directory.

    Returns:
        Path | None: Path to the newest MapData.sav or None if not found.
    """
    return max(save_dir.glob("*_MapData.sav"), key=lambda f: f.stat().st_mtime, default=None)


def auto_detect_savefile() -> Path | None:
    """Auto-detect the Foxhole MapData.sav file.

    Delegates the search to fs-sav, which looks in every known save location
    (Windows, WSL users and Steam/Proton libraries) and sorts newest first.

    Returns:
        Path | None: Path to the most recent save file, or None if not found.
    """
    saves = fs_sav.find_save_files()
    if not saves:
        return None
    return Path(saves[0]["path"])
