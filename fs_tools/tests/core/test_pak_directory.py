"""Tests for the directory the PAK file dialogs open in."""

from pathlib import Path
from unittest.mock import patch

import pytest

from fs_tools.core.pak_directory import default_pak_directory

_FIND_PAKS = "fs_tools.core.pak_directory.fs_assets.get_default_pak_directory"


def test_uses_the_steam_pak_directory_when_found(tmp_path: Path) -> None:
    """The game's PAK directory is the dialog's starting point when it is found."""
    with patch(_FIND_PAKS, return_value=tmp_path):
        assert default_pak_directory() == str(tmp_path)


def test_falls_back_to_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a Steam install holding the game, the working directory is used."""
    monkeypatch.chdir(tmp_path)

    with patch(_FIND_PAKS, return_value=None):
        assert default_pak_directory() == str(Path.cwd())
