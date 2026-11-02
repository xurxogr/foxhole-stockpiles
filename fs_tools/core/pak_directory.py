"""Directory the PAK file dialogs open in."""

from pathlib import Path

import fs_assets


def default_pak_directory() -> str:
    """Return the directory where a PAK file dialog should start.

    Returns:
        str: The game's PAK directory in the local Steam install, or the current
            working directory when it is not found.
    """
    return str(fs_assets.get_default_pak_directory() or Path.cwd())
