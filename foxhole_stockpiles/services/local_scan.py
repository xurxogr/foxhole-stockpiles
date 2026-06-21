"""Local scan service: run the OCR scanner and route the result to outputs.

This replaces the former HTTP round-trip to the FastAPI server. The OCR engine
runs in-process (``services.scanner.Scanner`` over the external ``fs_ocr`` Rust
engine) and the resulting :class:`Stockpile` is fanned out to the configured
output handlers via :class:`OutputCoordinator`.

Construct once (loads the engine) and reuse across captures.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.scanner import build_scanner

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from foxhole_stockpiles.core.settings.app_settings import AppSettings

logger = logging.getLogger(__name__)


class LocalScanService:
    """Scan images in-process and route results to the configured outputs."""

    def __init__(self, settings: AppSettings) -> None:
        """Initialize the local scan service.

        Args:
            settings (AppSettings): Application settings providing the scanner and
                output configuration.

        Raises:
            ValueError: If ``scanner.database_path`` is not configured.
            FileNotFoundError: If the configured database file does not exist.
        """
        self._scanner = build_scanner(settings.scanner)
        self._output_coordinator = OutputCoordinator(output_settings=settings.output)

    def scan(
        self,
        image: bytes | str | Path | NDArray[np.uint8],
        faction: ItemFaction | None = None,
    ) -> Stockpile:
        """Scan an image and route the detected stockpile to all output handlers.

        Args:
            image (bytes | str | Path | NDArray[np.uint8]): Image to scan (encoded
                bytes, a path, or a decoded BGR array).
            faction (ItemFaction | None): Optional faction filter. ``NEUTRAL`` or
                ``None`` applies no filter.

        Returns:
            Stockpile: The detected stockpile (also dispatched to outputs).
        """
        faction_filter = faction if faction != ItemFaction.NEUTRAL else None
        stockpile = self._scanner.scan_sync(image, faction=faction_filter)
        asyncio.run(self._output_coordinator.handle_output(stockpiles=[stockpile]))
        return stockpile
