"""Remember when each Discord webhook was last posted to.

It is kept apart from the configuration, which is the user's and is not rewritten for
a send, and it survives restarts, so a scan from the command line respects it too.
"""

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Final

from foxhole_stockpiles.core.settings.config_path import default_config_path
from foxhole_stockpiles.core.utils import write_private_file

_FILE_NAME: Final[str] = "discord_cooldowns.json"
_SECONDS_PER_MINUTE: Final[int] = 60
_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


def _state_path() -> Path:
    """Locate the file with the times.

    Returns:
        Path: The file, next to the default configuration.
    """
    return default_config_path().parent / _FILE_NAME


def _key(url: str) -> str:
    """Identify a webhook without storing its URL, which holds its credential.

    Args:
        url (str): The URL.

    Returns:
        str: Its hash.
    """
    return hashlib.sha256(url.encode()).hexdigest()


def _read_state(path: Path) -> dict[str, float]:
    """Read the times. Losing them only means that a post may come early.

    Args:
        path (Path): The file.

    Returns:
        dict[str, float]: The time of the last post of each webhook.
    """
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("Could not read the times of the Discord posts: %s", e)
        return {}
    if not isinstance(state, dict):
        return {}
    return {
        key: float(value)
        for key, value in state.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }


def seconds_until_allowed(url: str, minutes: int) -> float:
    """Tell how long a webhook has to wait for its next post.

    Args:
        url (str): The URL of the webhook.
        minutes (int): The minimum time between posts.

    Returns:
        float: The seconds left, 0 if it can post now.
    """
    if minutes <= 0:
        return 0.0
    with _LOCK:
        last = _read_state(_state_path()).get(_key(url))
    if last is None:
        return 0.0
    now = time.time()
    # A time in the future means the clock changed, and must not block posts for long.
    if last > now:
        return 0.0
    return max(0.0, last + minutes * _SECONDS_PER_MINUTE - now)


def record_post(url: str) -> None:
    """Remember that a webhook has just been posted to.

    What was posted is not undone by a failure here, so it is only logged.

    Args:
        url (str): The URL of the webhook.
    """
    path = _state_path()
    with _LOCK:
        state = {**_read_state(path), _key(url): time.time()}
        try:
            write_private_file(path=path, content=json.dumps(state))
        except OSError as e:
            logger.warning("Could not save the time of the Discord post: %s", e)
