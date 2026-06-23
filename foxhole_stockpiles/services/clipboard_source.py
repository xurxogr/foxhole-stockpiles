"""Shared clipboard reader used by both the GUI and the CLI.

The reader is a thin wrapper over ``pyperclip`` so that screenshot capture,
the GUI worker, and the ``fs clip`` CLI all read the system clipboard through
exactly one mechanism. Keeping a single seam avoids GUI/CLI divergence and
makes the source trivially mockable in tests.
"""

from __future__ import annotations

import logging

import pyperclip

logger = logging.getLogger(__name__)


class ClipboardSource:
    """Reads the current text contents of the system clipboard."""

    def read(self) -> str | None:
        """Return the current clipboard text.

        Returns:
            str | None: The clipboard contents, or None if the clipboard could
                not be read (e.g. no clipboard backend available).
        """
        try:
            text: str = pyperclip.paste()
            return text
        except Exception as e:  # noqa: BLE001 - backends raise varied/bare errors
            # pyperclip's platform backends don't all raise PyperclipException
            # (e.g. the WSL powershell backend raises a bare Exception on an
            # empty/unavailable clipboard), so catch broadly and treat any
            # read failure as "no clipboard content".
            logger.warning("Could not read clipboard: %s", e)
            return None
