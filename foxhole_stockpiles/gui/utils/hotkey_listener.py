"""Global hotkey listener backed by ``pynput``.

The listener runs in its own thread (managed by ``pynput``); the supplied
callback is invoked from that thread, so callers that touch Qt should hand in a
Qt signal's ``emit`` (delivered to the GUI thread via a queued connection).

``pynput`` is imported lazily so importing this module never fails on a headless
host; :meth:`HotkeyListener.start` raises if the backend cannot be loaded.
"""

from __future__ import annotations

import logging
import os
import platform
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def global_hotkeys_supported() -> bool:
    """Best-effort check whether global hotkeys can actually be captured here.

    Global hotkeys work on native Windows/macOS and on X11, but not under WSL
    (the Linux GUI used during development, where key events aren't delivered
    globally) nor when the ``pynput`` backend cannot be loaded (e.g. headless).

    Returns:
        bool: True if global hotkeys are expected to work in this environment.
    """
    # WSL tags the Linux kernel release with "microsoft" and exports WSL_DISTRO_NAME.
    if "microsoft" in platform.uname().release.lower() or os.environ.get("WSL_DISTRO_NAME"):
        return False

    try:
        from pynput import keyboard  # noqa: F401
    except Exception:
        return False

    return True


def to_global_hotkey(key: str) -> str:
    """Convert a human key spec to ``pynput`` ``GlobalHotKeys`` syntax.

    Single characters are passed through; named keys are wrapped in angle
    brackets. ``"+"`` separates combination members. For example ``"F9"`` becomes
    ``"<f9>"`` and ``"ctrl+s"`` becomes ``"<ctrl>+s"``.

    Args:
        key (str): The configured key spec (e.g. ``"F9"`` or ``"ctrl+shift+s"``).

    Returns:
        str: The hotkey string understood by ``pynput.keyboard.GlobalHotKeys``.

    Raises:
        ValueError: If ``key`` is empty.
    """
    parts = [part.strip() for part in key.split("+") if part.strip()]
    if not parts:
        raise ValueError("Hotkey spec is empty")

    # pynput names the platform "Meta"/"Super"/"Win" key "cmd".
    aliases = {"meta": "cmd", "super": "cmd", "win": "cmd"}

    tokens: list[str] = []
    for part in parts:
        if len(part) == 1:
            tokens.append(part.lower())
        else:
            name = aliases.get(part.lower(), part.lower())
            tokens.append(f"<{name}>")
    return "+".join(tokens)


class HotkeyListener:
    """Start and stop a single global hotkey binding."""

    def __init__(self, key: str, callback: Callable[[], None]) -> None:
        """Initialize the listener.

        Args:
            key (str): The configured key spec (e.g. ``"F9"``).
            callback (Callable[[], None]): Called (from the listener thread) when
                the hotkey fires.
        """
        self._hotkey = to_global_hotkey(key)
        self._callback = callback
        self._listener: Any = None

    def start(self) -> None:
        """Begin listening for the hotkey.

        Raises:
            RuntimeError: If the ``pynput`` backend cannot be loaded.
        """
        try:
            from pynput import keyboard
        except Exception as exc:  # ImportError or platform load failure
            raise RuntimeError("Global hotkeys are not available on this platform.") from exc

        self._listener = keyboard.GlobalHotKeys({self._hotkey: self._callback})
        self._listener.start()
        logger.debug("Hotkey listener started for %s", self._hotkey)

    def stop(self) -> None:
        """Stop listening for the hotkey (no-op if not started)."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.debug("Hotkey listener stopped")
