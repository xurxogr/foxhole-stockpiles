"""A broken translation file next to the executable must not stop the application."""

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from foxhole_stockpiles.i18n.translator import Translator, get_available_languages

_BROKEN_CONTENTS = [b"[1, 2]", b'"text"', b"{not json", b"\xff\xfe{}"]
_BROKEN_IDS = ["list", "string", "invalid-json", "not-utf8"]


@pytest.fixture
def user_dir(tmp_path: Path) -> Iterator[Path]:
    """Use a temporary directory for the user translations.

    Args:
        tmp_path (Path): Directory for the test.

    Yields:
        Path: The directory.
    """
    with patch(
        "foxhole_stockpiles.i18n.translator._get_user_translations_dir", return_value=tmp_path
    ):
        yield tmp_path


@pytest.mark.parametrize("content", _BROKEN_CONTENTS, ids=_BROKEN_IDS)
def test_a_broken_user_file_leaves_the_bundled_translations(user_dir: Path, content: bytes) -> None:
    """The bundled text keeps working."""
    (user_dir / "en.json").write_bytes(content)

    translator = Translator("en")

    assert translator("common.save") != "common.save"


@pytest.mark.parametrize("content", _BROKEN_CONTENTS, ids=_BROKEN_IDS)
def test_a_broken_user_file_keeps_the_bundled_language_name(user_dir: Path, content: bytes) -> None:
    """A broken override does not rename a language that is available anyway."""
    (user_dir / "en.json").write_bytes(content)

    assert dict(get_available_languages())["en"] == "English"


@pytest.mark.parametrize("content", _BROKEN_CONTENTS, ids=_BROKEN_IDS)
def test_a_broken_new_language_is_listed_by_its_code(user_dir: Path, content: bytes) -> None:
    """A language only a broken file provides shows its code, as it always did."""
    (user_dir / "xx.json").write_bytes(content)

    assert dict(get_available_languages())["xx"] == "xx"


def test_a_user_language_name_overrides_the_bundled_one(user_dir: Path) -> None:
    """A valid override still wins."""
    (user_dir / "en.json").write_text(json.dumps({"language_name": "Mine"}), encoding="utf-8")

    assert dict(get_available_languages())["en"] == "Mine"


def test_a_file_without_a_name_is_listed_by_its_code(user_dir: Path) -> None:
    """The name is optional in a new language."""
    (user_dir / "xx.json").write_text("{}", encoding="utf-8")

    assert dict(get_available_languages())["xx"] == "xx"
