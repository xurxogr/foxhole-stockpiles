"""Tests for how handlers.file builds output paths from stockpile data."""

from pathlib import Path

import pytest

from foxhole_stockpiles.handlers.file import FileOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem

_ITEM = StockpileItem(code="Rifle", quantity=1)


def _written_files(root: Path) -> list[str]:
    """List every file below a directory, relative to it.

    Args:
        root (Path): The directory to walk.

    Returns:
        list[str]: Sorted relative POSIX paths.
    """
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["..", ".", "...", " .. ", ". ."])
async def test_dot_only_name_stays_inside_the_output_directory(tmp_path: Path, name: str) -> None:
    """A stockpile named like a relative path segment cannot leave its directory."""
    base = tmp_path / "root" / "out"
    base.mkdir(parents=True)
    handler = FileOutputHandler(default_file_path=str(base / "{stockpile_name}" / "x.json"))

    await handler.handle([Stockpile(name=name, items=[_ITEM])])

    assert _written_files(tmp_path) == ["root/out/_/x.json"]


@pytest.mark.asyncio
async def test_separators_cannot_build_a_path(tmp_path: Path) -> None:
    """Path separators in a name never create extra directories."""
    handler = FileOutputHandler(default_file_path=str(tmp_path / "{stockpile_name}.json"))

    await handler.handle([Stockpile(name="../..\\evil", items=[_ITEM])])

    files = _written_files(tmp_path)
    assert len(files) == 1
    assert "/" not in files[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a:b", "a_b.json"),
        ('a<b>c"d|e?f*g', "a_b_c_d_e_f_g.json"),
        ("line\nbreak", "line_break.json"),
        ("NUL", "_NUL.json"),
        ("com1", "_com1.json"),
        ("Aux.old", "_Aux.old.json"),
        ("Депо", "Депо.json"),
    ],
)
async def test_names_windows_cannot_store_are_rewritten(
    tmp_path: Path, name: str, expected: str
) -> None:
    """Characters and device names Windows rejects never reach the path."""
    handler = FileOutputHandler(default_file_path=str(tmp_path / "{stockpile_name}"))

    await handler.handle([Stockpile(name=name, items=[_ITEM])])

    assert _written_files(tmp_path) == [expected]


@pytest.mark.asyncio
async def test_dotted_names_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """The extension comes from the template, not from a name that contains a dot."""
    handler = FileOutputHandler(default_file_path=str(tmp_path / "{stockpile_name}"))

    await handler.handle([Stockpile(name="base.v2", items=[_ITEM])])
    await handler.handle([Stockpile(name="base.v3", items=[_ITEM])])

    assert _written_files(tmp_path) == ["base.v2.json", "base.v3.json"]


def test_carriage_return_is_quoted_in_csv() -> None:
    """A carriage return ends a CSV row, so a value holding one must be quoted."""
    handler = FileOutputHandler()

    assert handler._escape_csv_value("a\rb", ",") == '"a\rb"'


def test_tab_prefixed_formula_is_neutralized_in_csv() -> None:
    """Spreadsheets skip leading whitespace, so it cannot hide a formula."""
    handler = FileOutputHandler()

    assert handler._escape_csv_value(" =1+1", ",") == "' =1+1"
