"""Utility functions for the stockpile system."""

import os
import sys
import tempfile
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


def write_private_file(path: Path, content: str) -> None:
    """Atomically replace a text file with one only its owner can read.

    The content goes to a temporary file in the same directory first, so a crash
    or a full disk leaves the previous file intact. On Windows the permission bits
    have little effect and the file relies on the ACLs of the user profile.

    Args:
        path (Path): The file to create or replace.
        content (str): The text to store, encoded as UTF-8.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file with mode 0600.
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


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
