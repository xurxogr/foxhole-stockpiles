"""Tests for the ``build-catalog`` command entry point (``catalog_builder.main``).

The extractor, catalog assembler and logging setup are mocked so the test drives
the argument handling and control flow without touching PAK files or real tools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fs_tools.commands.catalog_builder import catalog_builder as cb

_MODULE = "fs_tools.commands.catalog_builder.catalog_builder"
_FROM_EXTRACT = f"{_MODULE}.CatalogAssembler.from_extract_dir"


def _service() -> MagicMock:
    """Build a mock CatalogAssembler service returning a real catalog dict."""
    service = MagicMock()
    service.build_catalog.return_value = {"ItemX": {"code": "ItemX"}}
    service.get_stats.return_value = {"parsed": 1, "stockpilable": 1, "errors": 0}
    return service


async def test_main_with_extract_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With --extract-dir, extraction is skipped and the catalog is written."""
    out = tmp_path / "catalog.json"
    extract = tmp_path / "war"
    extract.mkdir()
    monkeypatch.setattr(sys, "argv", ["prog", "--extract-dir", str(extract), "--output", str(out)])

    with (
        patch.object(cb, "setup_logging"),
        patch(_FROM_EXTRACT, return_value=_service()) as ffe,
    ):
        await cb.main()

    ffe.assert_called_once()
    assert json.loads(out.read_text(encoding="utf-8")) == {"ItemX": {"code": "ItemX"}}


async def test_main_extracts_from_pak(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --extract-dir, the blueprint extractor runs first."""
    out = tmp_path / "catalog.json"
    monkeypatch.setattr(
        sys, "argv", ["prog", "--output", str(out), "--pak", str(tmp_path / "x.pak")]
    )
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=tmp_path / "extracted")
    extractor.stats = {"extracted": 5, "converted": 5}

    with (
        patch.object(cb, "setup_logging"),
        patch.object(cb, "BlueprintExtractor", return_value=extractor) as extractor_cls,
        patch(_FROM_EXTRACT, return_value=_service()),
    ):
        await cb.main()

    extractor_cls.assert_called_once()
    extractor.extract.assert_awaited_once()
    assert out.exists()


async def test_main_invalid_extract_dir_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid extraction directory exits with code 1."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--extract-dir", str(tmp_path / "war"), "--output", str(tmp_path / "o.json")],
    )

    with (
        patch.object(cb, "setup_logging"),
        patch(_FROM_EXTRACT, side_effect=FileNotFoundError("nope")),
        pytest.raises(SystemExit),
    ):
        await cb.main()


async def test_main_quiet_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The --quiet flag is accepted and the catalog is still written."""
    out = tmp_path / "catalog.json"
    extract = tmp_path / "war"
    extract.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--extract-dir", str(extract), "--output", str(out), "--quiet"],
    )

    with (
        patch.object(cb, "setup_logging"),
        patch(_FROM_EXTRACT, return_value=_service()),
    ):
        await cb.main()

    assert out.exists()
