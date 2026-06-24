"""Tests for the clipboard scan service (the GUI/CLI shared seam)."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.clipboard_parser import build_code_map
from foxhole_stockpiles.services.clipboard_scan import (
    ClipboardScanService,
    build_clipboard_scan_service,
)

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "catalog.json"

CATALOG: list[dict[str, Any]] = [
    {
        "CodeName": "RifleC",
        "DisplayName": "Argenti r.II Rifle",
        "FactionVariant": "EFactionId::Colonials",
    },
    {"CodeName": "RifleAmmo", "DisplayName": "7.62mm", "FactionVariant": None},
]

HEADER = "Terminus - Rising Loom - Seaport - Public - X: 0.45 Y: 0.66,2026.06.23-16.30.38"
EXPORT_A = f"{HEADER}\nArgenti r.II Rifle (Crate),32\n"
EXPORT_B = f"{HEADER}\n7.62mm (Crate),60\n"


class FakeSource:
    """A clipboard source returning a fixed (mutable) value."""

    def __init__(self, value: str | None = None) -> None:
        """Store the value the source returns."""
        self.value = value

    def read(self) -> str | None:
        """Return the current value."""
        return self.value


class FakeCoordinator:
    """Captures stockpiles routed through ``handle_output``."""

    def __init__(self) -> None:
        """Initialize the recorded-calls list."""
        self.calls: list[list[Stockpile]] = []

    async def handle_output(self, stockpiles: list[Stockpile], **_: Any) -> None:
        """Record a routed batch of stockpiles."""
        self.calls.append(stockpiles)


def _service(source: FakeSource) -> tuple[ClipboardScanService, FakeCoordinator]:
    coordinator = FakeCoordinator()
    service = ClipboardScanService(
        output_coordinator=coordinator,  # type: ignore[arg-type]
        code_map=build_code_map(CATALOG),
        source=source,  # type: ignore[arg-type]
    )
    return service, coordinator


def test_scan_once_routes_current_clipboard() -> None:
    """scan_once parses and routes whatever is currently on the clipboard."""
    service, coordinator = _service(FakeSource(EXPORT_A))
    stockpile = asyncio.run(service.scan_once())
    assert stockpile is not None
    assert len(coordinator.calls) == 1
    assert coordinator.calls[0][0].items[0].code == "RifleC"


def test_scan_once_ignores_non_stockpile() -> None:
    """Non-stockpile clipboard text is not routed."""
    service, coordinator = _service(FakeSource("random copied text"))
    assert asyncio.run(service.scan_once()) is None
    assert coordinator.calls == []


def test_poll_emits_only_on_change() -> None:
    """Polling emits a new export once, then stays silent until content changes."""
    source = FakeSource(EXPORT_A)
    service, coordinator = _service(source)

    # First poll: new content -> emitted.
    assert asyncio.run(service.poll()) is not None
    # Same content -> no re-emit.
    assert asyncio.run(service.poll()) is None
    # Changed content -> emitted again.
    source.value = EXPORT_B
    result = asyncio.run(service.poll())
    assert result is not None
    assert len(coordinator.calls) == 2
    assert coordinator.calls[1][0].items[0].code == "RifleAmmo"


def test_poll_ignores_changed_non_stockpile() -> None:
    """A clipboard change that is not a stockpile export is not emitted."""
    source = FakeSource("not a stockpile")
    service, coordinator = _service(source)
    assert asyncio.run(service.poll()) is None
    assert coordinator.calls == []


def test_prime_suppresses_existing_clipboard() -> None:
    """After prime(), the content already present does not emit on next poll."""
    source = FakeSource(EXPORT_A)
    service, coordinator = _service(source)

    service.prime()  # Treat EXPORT_A as already seen.
    assert asyncio.run(service.poll()) is None
    assert coordinator.calls == []

    # A genuinely new export still emits.
    source.value = EXPORT_B
    assert asyncio.run(service.poll()) is not None
    assert len(coordinator.calls) == 1


def test_build_service_requires_catalog_file() -> None:
    """Building without a configured catalog file raises ValueError."""
    settings = AppSettings()
    settings.database_builder.catalog_file = None
    with pytest.raises(ValueError, match="catalog_file"):
        build_clipboard_scan_service(settings)


def test_build_service_from_settings() -> None:
    """A configured catalog file yields a ready service."""
    settings = AppSettings()
    settings.database_builder.catalog_file = CATALOG_PATH
    service = build_clipboard_scan_service(settings)
    assert isinstance(service, ClipboardScanService)
