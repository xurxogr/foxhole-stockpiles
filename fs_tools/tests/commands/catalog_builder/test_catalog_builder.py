"""Tests for the ``build-catalog`` command entry point (``catalog_builder.run``).

The extractor, catalog assembler and logging setup are mocked so the test drives
the argument handling and control flow without touching PAK files or real tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from fs_tools.commands.catalog_builder import catalog_builder as cb

_MODULE = "fs_tools.commands.catalog_builder.catalog_builder"
_FROM_EXTRACT = f"{_MODULE}.CatalogAssembler.from_extract_dir"


def _service() -> MagicMock:
    """Build a mock CatalogAssembler service returning a real catalog dict."""
    service = MagicMock()
    service.build_catalog.return_value = {"ItemX": {"code": "ItemX"}}
    service.get_stats.return_value = {"parsed": 1, "stockpilable": 1, "errors": 0}
    return service


async def test_run_with_extract_dir(tmp_path: Path) -> None:
    """With extract_dir, extraction is skipped and the catalog is written."""
    out = tmp_path / "catalog.json"
    extract = tmp_path / "war"
    extract.mkdir()

    with (
        patch.object(cb, "setup_logging"),
        patch(_FROM_EXTRACT, return_value=_service()) as ffe,
    ):
        await cb.run(extract_dir=extract, output=out)

    ffe.assert_called_once()
    assert json.loads(out.read_text(encoding="utf-8")) == {"ItemX": {"code": "ItemX"}}


async def test_run_extracts_from_pak(tmp_path: Path) -> None:
    """Without extract_dir, the blueprint extractor runs first."""
    out = tmp_path / "catalog.json"
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=tmp_path / "extracted")
    extractor.stats = {"extracted": 5, "converted": 5}

    with (
        patch.object(cb, "setup_logging"),
        patch.object(cb, "BlueprintExtractor", return_value=extractor) as extractor_cls,
        patch(_FROM_EXTRACT, return_value=_service()),
    ):
        await cb.run(output=out, pak=tmp_path / "x.pak")

    extractor_cls.assert_called_once()
    extractor.extract.assert_awaited_once()
    assert out.exists()


async def test_run_invalid_extract_dir_exits(tmp_path: Path) -> None:
    """An invalid extraction directory exits with code 1."""
    with (
        patch.object(cb, "setup_logging"),
        patch(_FROM_EXTRACT, side_effect=FileNotFoundError("nope")),
        pytest.raises(typer.Exit),
    ):
        await cb.run(extract_dir=tmp_path / "war", output=tmp_path / "o.json")


async def test_run_quiet_flag(tmp_path: Path) -> None:
    """The quiet flag is accepted and the catalog is still written."""
    out = tmp_path / "catalog.json"
    extract = tmp_path / "war"
    extract.mkdir()

    with (
        patch.object(cb, "setup_logging"),
        patch(_FROM_EXTRACT, return_value=_service()),
    ):
        await cb.run(extract_dir=extract, output=out, quiet=True)

    assert out.exists()
