"""Tests for core.utils.write_private_file."""

import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.utils import write_private_file


def test_creates_parents_and_writes_content(tmp_path: Path) -> None:
    """Missing parent directories are created and the text is stored as UTF-8."""
    target = tmp_path / "a" / "b" / "config.json"

    write_private_file(target, "héllo")

    assert target.read_text(encoding="utf-8") == "héllo"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_file_is_readable_only_by_its_owner(tmp_path: Path) -> None:
    """A new file and a replaced, wider-open one both end up owner-only."""
    target = tmp_path / "config.json"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o644)

    write_private_file(target, "new")

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_failed_write_keeps_the_previous_file(tmp_path: Path) -> None:
    """A crash during the write leaves the old content and no temp file behind."""
    target = tmp_path / "config.json"
    target.write_text("old", encoding="utf-8")

    with (
        patch.object(os, "replace", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        write_private_file(target, "new")

    assert target.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]
