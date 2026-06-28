"""Clipboard scan service: read the clipboard, parse it, and route the result.

This is the clipboard counterpart of :class:`services.local_scan.LocalScanService`.
It ties together the shared :class:`ClipboardSource`, the pure
:func:`parse_clipboard`, and the :class:`OutputCoordinator`, and is reused by
both the GUI workers and the ``fs clip`` CLI so the two never diverge.

Two entry points mirror the manual/monitor modes:

* :meth:`scan_once` always parses the *current* clipboard (the manual hotkey /
  ``--once`` path).
* :meth:`poll` only acts when the clipboard content *changed* since the last
  poll and parses as a stockpile (the monitor path), so unchanged or unrelated
  clipboard content is ignored.
"""

from __future__ import annotations

import logging

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.clipboard_parser import (
    ClipboardCodeMap,
    build_code_map_from_file,
    parse_clipboard,
)
from foxhole_stockpiles.services.clipboard_source import ClipboardSource
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator, OutputResponse

logger = logging.getLogger(__name__)


class ClipboardScanService:
    """Reads, parses, and routes Foxhole stockpile clipboard exports."""

    def __init__(
        self,
        output_coordinator: OutputCoordinator,
        code_map: ClipboardCodeMap,
        source: ClipboardSource | None = None,
    ) -> None:
        """Initialize the clipboard scan service.

        Args:
            output_coordinator (OutputCoordinator): Routes parsed stockpiles to
                the configured output handlers.
            code_map (ClipboardCodeMap): Display-name -> code lookup.
            source (ClipboardSource | None): Clipboard reader. Defaults to a new
                :class:`ClipboardSource`.
        """
        self._output_coordinator = output_coordinator
        self._code_map = code_map
        self._source = source or ClipboardSource()
        self._last_text: str | None = None
        # The output handlers' response from the most recent routed stockpile,
        # surfaced so the GUI can show it. None when nothing was routed.
        self.last_output: OutputResponse = None

    def prime(self) -> None:
        """Seed the last-seen clipboard without emitting.

        Called when starting monitor mode so the content already on the
        clipboard is treated as "already seen"; only a subsequent new export
        triggers an emit.
        """
        self._last_text = self._source.read()

    async def scan_once(self) -> Stockpile | None:
        """Parse the current clipboard and route it if it is a stockpile.

        Returns:
            Stockpile | None: The parsed stockpile, or None if the clipboard
                does not hold a stockpile export.
        """
        text = self._source.read()
        self._last_text = text
        return await self._route(parse_clipboard(text, self._code_map))

    async def poll(self) -> Stockpile | None:
        """Parse and route only when the clipboard changed to a new export.

        Returns:
            Stockpile | None: The parsed stockpile when the clipboard content
                changed and matched the expected structure, else None.
        """
        text = self._source.read()
        if not text or text == self._last_text:
            return None
        self._last_text = text
        return await self._route(parse_clipboard(text, self._code_map))

    async def _route(self, stockpile: Stockpile | None) -> Stockpile | None:
        """Fan a parsed stockpile out to the output handlers.

        Args:
            stockpile (Stockpile | None): The parsed stockpile, if any.

        Returns:
            Stockpile | None: The stockpile passed in, for caller convenience.
        """
        self.last_output = None
        if stockpile is not None:
            self.last_output = await self._output_coordinator.handle_output([stockpile])
        return stockpile


def build_clipboard_scan_service(
    settings: AppSettings,
    output_coordinator: OutputCoordinator | None = None,
) -> ClipboardScanService:
    """Build a clipboard scan service from application settings.

    Args:
        settings (AppSettings): Application settings (for the catalog and output).
        output_coordinator (OutputCoordinator | None): Optional pre-built
            coordinator; one is created from ``settings.output`` when omitted.

    Returns:
        ClipboardScanService: A ready-to-use service.

    Raises:
        ValueError: If no catalog file is configured.
        FileNotFoundError: If the configured catalog file does not exist.
    """
    catalog_path = settings.database_builder.catalog_file
    if catalog_path is None:
        raise ValueError("database_builder.catalog_file must be configured for clipboard scanning")

    coordinator = output_coordinator or OutputCoordinator(settings.output)
    code_map = build_code_map_from_file(catalog_path)
    return ClipboardScanService(output_coordinator=coordinator, code_map=code_map)
