"""Log files can hold private data, so only their owner can read them."""

import logging
import stat
import sys
from collections.abc import Iterator
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from foxhole_stockpiles.core.logging import (
    APP_FILE_HANDLER_NAME,
    _get_handler_by_name,
    _remove_handler_by_name,
    setup_logging,
)
from foxhole_stockpiles.core.settings.sections.logging import LoggingSettings

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows relies on the ACLs of the user profile"
)

_PRIVATE_MODE = 0o600
_OPEN_MODE = 0o644


def _mode(path: Path) -> int:
    """Read the permission bits of a file.

    Args:
        path (Path): The file.

    Returns:
        int: Its permission bits.
    """
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def log_path(tmp_path: Path) -> Iterator[Path]:
    """Provide a log path, removing the file handler set up with it afterwards.

    Args:
        tmp_path (Path): Directory for the test.

    Yields:
        Path: The log file path.
    """
    root = logging.getLogger()
    level = root.level
    yield tmp_path / "logs" / "app.log"
    _remove_handler_by_name(root, APP_FILE_HANDLER_NAME)
    root.setLevel(level)


@pytest.mark.parametrize("rotate", [False, True], ids=["plain", "rotating"])
def test_a_new_log_file_is_private(log_path: Path, rotate: bool) -> None:
    """Neither kind of log file is created readable by others."""
    setup_logging(LoggingSettings(log_file=str(log_path), rotate_logs=rotate))

    assert _mode(log_path) == _PRIVATE_MODE


@pytest.mark.parametrize("rotate", [False, True], ids=["plain", "rotating"])
def test_an_existing_log_file_becomes_private(log_path: Path, rotate: bool) -> None:
    """A log left by an earlier version does not stay readable by others."""
    log_path.parent.mkdir(parents=True)
    log_path.write_text("old\n", encoding="utf-8")
    log_path.chmod(_OPEN_MODE)

    setup_logging(LoggingSettings(log_file=str(log_path), rotate_logs=rotate))

    assert _mode(log_path) == _PRIVATE_MODE
    assert log_path.read_text(encoding="utf-8") == "old\n"


def test_the_file_opened_by_a_rotation_is_private(log_path: Path) -> None:
    """Rotating opens a new file, which must not fall back to the default mode."""
    setup_logging(LoggingSettings(log_file=str(log_path), rotate_logs=True))
    handler = _get_handler_by_name(logging.getLogger(), APP_FILE_HANDLER_NAME)
    assert isinstance(handler, TimedRotatingFileHandler)

    handler.doRollover()

    assert _mode(log_path) == _PRIVATE_MODE
    rotated = [path for path in log_path.parent.iterdir() if path != log_path]
    assert [_mode(path) for path in rotated] == [_PRIVATE_MODE]
