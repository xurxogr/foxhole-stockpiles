"""Capture the Foxhole game window as an image.

This is the runtime's screenshot source: it locates the Foxhole window (matched
by title prefix), verifies it is the active, non-minimized window on any monitor,
and grabs its client area as PNG bytes ready for the OCR scanner.

Capture is Windows-only: the window-management library (``pywinctl``) comes from
the ``capture`` extra, which only installs on Windows. Elsewhere, or without the
extra, :func:`capture_supported` is False and :func:`capture_window` raises
:class:`CaptureError` with a user-friendly message.
"""

from __future__ import annotations

import io
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

from foxhole_stockpiles.models.stockpile import Stockpile

try:
    import pywinctl

    PYWINCTL_AVAILABLE = True
except ImportError:  # the Windows-only `capture` extra is not installed
    PYWINCTL_AVAILABLE = False

logger = logging.getLogger(__name__)

#: ``sys.platform`` value of the only platform capture is shipped for.
CAPTURE_PLATFORM = "win32"

# The Foxhole game window is titled "War"; capture targets that window.
_WINDOW_TITLE_PREFIX = "War"

# Characters not allowed in the generated screenshot filenames.
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class CaptureError(RuntimeError):
    """Raised when the Foxhole window cannot be captured."""


def save_screenshot(
    image: bytes,
    folder: str | Path,
    stockpile: Stockpile | None = None,
) -> Path | None:
    """Save a captured screenshot under a per-day subfolder of ``folder``.

    The filename is the capture time (``HHMMSS``) followed by the stockpile
    type, name and resolution when available, e.g.
    ``143205_Seaport_Logi_1920x1080.png``.

    Args:
        image (bytes): The captured PNG bytes.
        folder (str | Path): Destination folder. An empty value disables saving.
        stockpile (Stockpile | None): Scan result used to build a descriptive
            filename. Optional.

    Returns:
        Path | None: The written file path, or None when ``folder`` is empty.
    """
    if not folder:
        return None

    now = datetime.now()
    day_dir = Path(folder).expanduser() / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    parts = [now.strftime("%H%M%S")]
    if stockpile is not None:
        for value in (getattr(stockpile, "type", None), stockpile.name, stockpile.resolution):
            text = str(value).strip() if value else ""
            if text:
                parts.append(text)

    stem = _UNSAFE_FILENAME.sub("-", "_".join(parts)).strip("-_") or now.strftime("%H%M%S")
    path = day_dir / f"{stem}.png"
    path.write_bytes(image)
    logger.debug("Saved screenshot to %s", path)
    return path


def capture_supported(platform: str = sys.platform) -> bool:
    """Report whether the Foxhole window can be captured on this machine.

    Args:
        platform (str): The ``sys.platform`` value to check. Defaults to the
            running interpreter's platform.

    Returns:
        bool: True on Windows with the ``capture`` extra installed.
    """
    return platform == CAPTURE_PLATFORM and PYWINCTL_AVAILABLE


def capture_window() -> bytes:
    """Capture the active Foxhole window and return it as PNG bytes.

    Returns:
        bytes: The captured window client area encoded as PNG.

    Raises:
        CaptureError: If capture is not supported here, no matching window
            is found, or the window is minimized or not the active window.
    """
    if not capture_supported():
        raise CaptureError(
            "Screenshot capture is not available: it requires Windows with the "
            "'capture' extra installed."
        )

    prefix = _WINDOW_TITLE_PREFIX
    try:
        windows = pywinctl.getWindowsWithTitle(prefix, condition=pywinctl.Re.STARTSWITH)
    except Exception as exc:
        raise CaptureError(f"Could not query windows titled '{prefix}*': {exc}") from exc

    if not windows:
        raise CaptureError(f"No window titled '{prefix}*' found. Is Foxhole running?")

    window = windows[0]

    if getattr(window, "isMinimized", False):
        raise CaptureError("The Foxhole window is minimized; restore it before capturing.")

    if not getattr(window, "isActive", False):
        raise CaptureError("The Foxhole window must be the active window to capture it.")

    region = window.getClientFrame()
    image = ImageGrab.grab(bbox=region, all_screens=True)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    logger.debug("Captured Foxhole window region %s", region)
    return buffer.getvalue()
