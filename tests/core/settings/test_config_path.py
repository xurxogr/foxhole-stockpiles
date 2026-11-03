"""The old config file moves when the settings are read, not when a module is imported."""

import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings import config_path as module

_LEGACY_NAME = ".fs_config"
_RELATIVE_CONFIG = Path("foxhole-stockpiles") / "config.json"


def _run_python(code: str, home: Path) -> None:
    """Run code in a new interpreter whose home directory is ``home``.

    Args:
        code (str): The code to run.
        home (Path): The home directory it sees.
    """
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
    }
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


def test_importing_the_settings_does_not_move_the_old_config(tmp_path: Path) -> None:
    """Importing a module has no effect on the files of the user."""
    legacy = tmp_path / _LEGACY_NAME
    legacy.write_text("{}", encoding="utf-8")

    _run_python("import foxhole_stockpiles.core.settings", home=tmp_path)

    assert legacy.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="The config directory comes from APPDATA")
def test_reading_the_settings_moves_the_old_config_and_uses_it(tmp_path: Path) -> None:
    """The first read finds the old content at the new location."""
    legacy = tmp_path / _LEGACY_NAME
    legacy.write_text('{"gui": {"language": "es"}}', encoding="utf-8")

    _run_python(
        "from foxhole_stockpiles.core.settings import AppSettings\n"
        "assert AppSettings().gui.language == 'es'\n",
        home=tmp_path,
    )

    assert not legacy.exists()
    assert (tmp_path / ".config" / _RELATIVE_CONFIG).exists()


def test_a_failed_move_does_not_stop_the_application(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The old file stays where it is and the reason is logged."""
    legacy = tmp_path / _LEGACY_NAME
    legacy.write_text("{}", encoding="utf-8")
    target = tmp_path / "config.json"

    with (
        patch.object(module, "LEGACY_CONFIG_PATH", legacy),
        patch.object(module, "default_config_path", return_value=target),
        patch.object(Path, "replace", side_effect=PermissionError("in use")),
        caplog.at_level(logging.WARNING),
    ):
        module.migrate_legacy_config_file(target)

    assert legacy.exists()
    assert "in use" in caplog.text
