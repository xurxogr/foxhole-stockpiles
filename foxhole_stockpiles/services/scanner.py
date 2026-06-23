"""Scanner seam over the external Rust ``fs_ocr`` engine.

This is the single point where ``foxhole_stockpiles`` talks to the OCR engine.
The external ``fs-ocr`` package returns its own ``Stockpile`` / ``StockpileItem``
types; this module adapts them to ``foxhole_stockpiles.models`` so the rest of
the runtime is unaware of the engine.

The external engine is synchronous (pure Rust); ``scan`` runs it in a worker
thread so callers keep an async interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import fs_ocr
import numpy as np

from foxhole_stockpiles.core.image_io import decode_bgr, read_bgr
from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.item_candidate import ItemCandidate
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# External StockpileType member name (as emitted by ``to_json``) -> runtime type.
# The external enum collapses base tiers; map them to the tier-1 runtime member.
_EXTERNAL_TYPE_BY_NAME: dict[str, StockpileType] = {
    "AircraftDepot": StockpileType.AIRCRAFT_DEPOT,
    "BmsLonghook": StockpileType.BMS_LONGHOOK,
    "BorderBase": StockpileType.BORDER_BASE,
    "BunkerBase": StockpileType.BUNKER_BASE_1,
    "Encampment": StockpileType.ENCAMPMENT,
    "Keep": StockpileType.KEEP,
    "RelicBase": StockpileType.RELIC_BASE,
    "SafeHouse": StockpileType.SAFE_HOUSE,
    "Seaport": StockpileType.SEAPORT,
    "StorageDepot": StockpileType.STORAGE_DEPOT,
    "TownBase": StockpileType.TOWN_BASE_1,
    "UndergroundFortress": StockpileType.UNDERGROUND_FORTRESS,
    "Undefined": StockpileType.UNDEFINED,
}

# Runtime faction -> external faction filter string (None = no filter).
_FACTION_TO_EXTERNAL: dict[ItemFaction, str] = {
    ItemFaction.WARDENS: "wardens",
    ItemFaction.COLONIALS: "colonials",
}


def _coerce_image(image: bytes | str | Path | NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Coerce supported image inputs to a BGR numpy array.

    Args:
        image (bytes | str | Path | NDArray[np.uint8]): Encoded image bytes, a
            path to an image file, or an already-decoded BGR array.

    Returns:
        NDArray[np.uint8]: Decoded BGR image array.

    Raises:
        ValueError: If the image cannot be decoded or read.
    """
    if isinstance(image, bytes):
        decoded = decode_bgr(image)
        if decoded is None:
            raise ValueError("Failed to decode image bytes")
        return decoded
    if isinstance(image, str | Path):
        loaded = read_bgr(image)
        if loaded is None:
            raise ValueError(f"Failed to read image: {image}")
        return loaded
    return np.asarray(image, dtype=np.uint8)


def to_runtime_stockpile(result: fs_ocr.Stockpile) -> Stockpile:
    """Adapt an external ``fs_ocr.Stockpile`` to the runtime model.

    Args:
        result (fs_ocr.Stockpile): A stockpile returned by the external engine.

    Returns:
        Stockpile: The equivalent ``foxhole_stockpiles`` stockpile.
    """
    payload = json.loads(result.to_json())
    type_name = payload.get("type") or "Undefined"

    items = [
        StockpileItem(
            code=item.code,
            quantity=item.quantity,
            crated=item.crated,
            confidence=item.confidence,
            x=item.x,
            y=item.y,
            candidates=(
                [ItemCandidate(code=c.code, confidence=c.confidence) for c in item.candidates]
                if item.candidates
                else None
            ),
        )
        for item in result.items
    ]
    errors = list(result.errors) or None

    return Stockpile(
        name=result.name or "",
        type=_EXTERNAL_TYPE_BY_NAME.get(type_name, StockpileType.UNDEFINED),
        is_reserve=result.is_reserve,
        items=items,
        shard=result.shard,
        ingame_timestamp=result.ingame_timestamp,
        resolution=result.resolution,
        errors=errors,
    )


class Scanner:
    """Runtime-facing wrapper around the external ``fs_ocr.StockpileScanner``.

    Construct once, scan many images. Adapts engine output to the runtime
    ``Stockpile`` model.
    """

    def __init__(self, settings: ScannerSettings) -> None:
        """Initialize the scanner from runtime scanner settings.

        Args:
            settings (ScannerSettings): Runtime scanner configuration.

        Raises:
            ValueError: If ``database_path`` is not configured.
            FileNotFoundError: If the configured database file does not exist.
        """
        if settings.database_path is None:
            raise ValueError("scanner.database_path must be configured")
        if not Path(settings.database_path).exists():
            raise FileNotFoundError(f"Database not found: {settings.database_path}")

        self._scanner = fs_ocr.StockpileScanner(database_path=str(settings.database_path))
        self._scanner.set_config(fs_ocr.ScanConfig(confidence_gap=settings.confidence_gap))

    async def scan(
        self,
        image: bytes | str | Path | NDArray[np.uint8],
        faction: ItemFaction | None = None,
    ) -> Stockpile:
        """Scan an image and return the detected stockpile.

        Args:
            image (bytes | str | Path | NDArray[np.uint8]): Image to scan.
            faction (ItemFaction | None): Optional faction filter. ``NEUTRAL`` or
                ``None`` applies no filter.

        Returns:
            Stockpile: The detected stockpile with items and metadata.
        """
        img = _coerce_image(image)
        ext_faction = _FACTION_TO_EXTERNAL.get(faction) if faction else None
        result = await asyncio.to_thread(self._scanner.scan, img, ext_faction)
        return to_runtime_stockpile(result)

    def scan_sync(
        self,
        image: bytes | str | Path | NDArray[np.uint8],
        faction: ItemFaction | None = None,
    ) -> Stockpile:
        """Synchronous variant of :meth:`scan` for non-async callers.

        Args:
            image (bytes | str | Path | NDArray[np.uint8]): Image to scan.
            faction (ItemFaction | None): Optional faction filter.

        Returns:
            Stockpile: The detected stockpile with items and metadata.
        """
        img = _coerce_image(image)
        ext_faction = _FACTION_TO_EXTERNAL.get(faction) if faction else None
        return to_runtime_stockpile(self._scanner.scan(img, ext_faction))


def build_scanner(settings: ScannerSettings) -> Scanner:
    """Build a :class:`Scanner` from runtime scanner settings.

    Args:
        settings (ScannerSettings): Runtime scanner configuration.

    Returns:
        Scanner: A ready-to-use scanner instance.
    """
    return Scanner(settings)
