"""Opening of log files that only their owner can read."""

import os
from pathlib import Path
from typing import Final, TextIO, cast

_PRIVATE_MODE: Final[int] = 0o600


def open_private_log(path: str, mode: str, encoding: str | None, errors: str | None) -> TextIO:
    """Open a log file readable only by its owner, whether it is new or not.

    Debug logs can hold stockpile data and whatever a library chooses to print. On
    Windows the permission bits have little effect and the file relies on the ACLs
    of the user profile.

    Args:
        path (str): The log file.
        mode (str): The open mode of the logging handler.
        encoding (str | None): The text encoding.
        errors (str | None): The encoding error policy.

    Returns:
        TextIO: The open stream.
    """
    stream = open(  # noqa: SIM115 - the logging handler owns and closes the stream
        path,
        mode,
        encoding=encoding,
        errors=errors,
        opener=lambda name, flags: os.open(name, flags, _PRIVATE_MODE),
    )
    Path(path).chmod(_PRIVATE_MODE)
    return cast(TextIO, stream)
