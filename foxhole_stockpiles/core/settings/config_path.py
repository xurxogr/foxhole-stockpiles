"""Resolution and one-time migration of the on-disk config file location."""

from pathlib import Path

import platformdirs

_APP_NAME = "foxhole-stockpiles"

LEGACY_CONFIG_PATH = Path("~/.fs_config").expanduser()


def default_config_path() -> Path:
    """Return the platform-appropriate config file path.

    Returns:
        Path: ``<platform config dir>/foxhole-stockpiles/config.json``.
    """
    return Path(platformdirs.user_config_dir(_APP_NAME)) / "config.json"


def migrate_legacy_config_file(target_path: Path) -> None:
    """Move a pre-existing legacy ``~/.fs_config`` file to its new location.

    Only acts when ``target_path`` is the real platform default (so pointing
    ``AppSettings`` at an isolated path, e.g. in tests, never touches the
    legacy file), the legacy file exists, and nothing already lives at the
    new location. Safe to call unconditionally since it is a no-op otherwise.

    Args:
        target_path (Path): The config path the caller is about to use.
    """
    if target_path != default_config_path():
        return
    if target_path.exists() or not LEGACY_CONFIG_PATH.exists():
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_CONFIG_PATH.replace(target_path)
    target_path.chmod(0o600)
