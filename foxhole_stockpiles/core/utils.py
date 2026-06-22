"""Utility functions for the stockpile system."""

import ctypes
import gc
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_subprocess_kwargs() -> dict[str, Any]:
    """Get platform-specific kwargs for subprocess calls to hide console windows.

    On Windows, this returns kwargs to prevent CMD windows from appearing
    when spawning subprocesses in GUI mode.

    Returns:
        dict[str, Any]: Kwargs to pass to subprocess.run() or create_subprocess_exec()
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


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


def malloc_trim(pad: int = 0) -> int:
    """Force glibc to return free memory to the operating system.

    This calls the glibc malloc_trim() function which releases free memory from the heap
    back to the system. This is useful after processing large data structures to prevent
    memory fragmentation from keeping process RSS high.

    On Linux with glibc, this can significantly reduce memory usage after freeing large
    allocations (numpy arrays, images, etc.) that would otherwise stay in malloc's
    internal pools.

    Args:
        pad (int): Amount of free space to leave untrimmed in bytes (default: 0)

    Returns:
        int: 1 if memory was released, 0 if not, -1 if malloc_trim is unavailable

    Note:
        - Only works on Linux with glibc
        - Has no effect on other platforms (returns -1)
        - Should be called after gc.collect() for best results
    """
    logger = logging.getLogger(__name__)
    try:
        libc = ctypes.CDLL("libc.so.6")
        result = libc.malloc_trim(pad)
        logger.debug("malloc_trim() returned: %d", result)
        return int(result)
    except (OSError, AttributeError) as e:
        logger.debug("malloc_trim() not available: %s", e)
        return -1


def force_memory_release() -> dict[str, Any]:
    """Force Python garbage collection and system memory release.

    This performs a full garbage collection cycle and then attempts to release
    freed memory back to the operating system via malloc_trim().

    Returns:
        dict[str, Any]: Statistics about the memory release operation
            - gc_collected: Number of objects collected by garbage collector
            - malloc_trimmed: 1 if memory was released, 0 if not, -1 if unavailable
    """
    logger = logging.getLogger(__name__)

    # Force full garbage collection
    collected = gc.collect()
    logger.debug("Garbage collector freed %d objects", collected)

    # Attempt to release memory to OS
    trimmed = malloc_trim()

    return {
        "gc_collected": collected,
        "malloc_trimmed": trimmed,
    }


# ==================== Savefile Locator Utilities ====================


def get_default_savefile_dir() -> Path | None:
    """Get the default Foxhole save file directory based on OS.

    Returns:
        Path | None: Default save games directory or None if not found.
    """
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            save_dir = Path(local_appdata) / "Foxhole" / "Saved" / "SaveGames"
            if save_dir.exists():
                return save_dir
    elif sys.platform == "linux":
        # WSL path - try common WSL mount points
        wsl_users = Path("/mnt/c/Users")
        if wsl_users.exists():
            try:
                for user_dir in wsl_users.iterdir():
                    try:
                        wsl_path = (
                            user_dir / "AppData" / "Local" / "Foxhole" / "Saved" / "SaveGames"
                        )
                        if wsl_path.exists():
                            return wsl_path
                    except PermissionError:
                        continue
            except PermissionError:
                pass

        # Native Linux (Proton/Wine)
        home = Path.home()
        proton_path = (
            home
            / ".steam"
            / "steam"
            / "steamapps"
            / "compatdata"
            / "505460"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "AppData"
            / "Local"
            / "Foxhole"
            / "Saved"
            / "SaveGames"
        )
        if proton_path.exists():
            return proton_path
    return None


def find_mapdata_file(save_dir: Path) -> Path | None:
    """Find the MapData.sav file in the save directory.

    Args:
        save_dir (Path): Save games directory.

    Returns:
        Path | None: Path to MapData.sav or None if not found.
    """
    for f in save_dir.glob("*_MapData.sav"):
        return f
    return None


def auto_detect_savefile() -> Path | None:
    """Auto-detect the Foxhole MapData.sav file.

    Returns:
        Path | None: Path to the detected save file, or None if not found.
    """
    save_dir = get_default_savefile_dir()
    if save_dir:
        return find_mapdata_file(save_dir)
    return None
