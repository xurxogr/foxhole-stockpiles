"""Shared pytest fixtures for fs_tools tests.

Re-exports the project-wide fixtures defined in ``tests/conftest.py`` so the
moved fs_tools tests keep access to them.
"""

from collections.abc import Callable, Iterator
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from foxhole_stockpiles.i18n import get_translator, set_translations_resource
from tests.conftest import (  # noqa: F401
    isolate_app_settings,
    mock_catalog_file,
    mock_color_image_array,
    mock_discord_webhook,
    mock_image_array,
    mock_pak_file,
    reset_logging,
    sample_catalog_data,
    temp_dir,
)

_MAIN_TRANSLATIONS = "foxhole_stockpiles/i18n/translations"
_TOOLS_TRANSLATIONS = "fs_tools/i18n/translations"


def _fail_on_dialog(name: str) -> Callable[..., object]:
    """Build a stand-in that fails the test when a native dialog is invoked.

    Args:
        name (str): Qualified name of the dialog call being guarded.

    Returns:
        Callable[..., object]: A function that raises AssertionError when called.
    """

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            f"Unexpected native dialog: {name} was called without being patched. "
            "Patch it explicitly in the test, or fix the code path that triggers it."
        )

    return _raise


@pytest.fixture(autouse=True)
def fail_on_unpatched_dialogs() -> Iterator[None]:
    """Make any unpatched native dialog call fail the test loudly.

    GUI code calls ``QMessageBox`` / ``QFileDialog`` static methods that open
    modal, blocking dialogs. A test that reaches such a call without patching it
    would pop a real window (and hang) in a developer/CI run. Rather than
    silently returning a default — which hides the unexpected interaction — we
    raise so the test fails and the author either patches the dialog or fixes
    the code path. Tests that legitimately exercise a dialog patch the specific
    call locally, which overrides this guard.

    Yields:
        None: Control to the test while the dialog guards are active.
    """
    with (
        patch.object(QMessageBox, "warning", side_effect=_fail_on_dialog("QMessageBox.warning")),
        patch.object(QMessageBox, "critical", side_effect=_fail_on_dialog("QMessageBox.critical")),
        patch.object(
            QMessageBox, "information", side_effect=_fail_on_dialog("QMessageBox.information")
        ),
        patch.object(QMessageBox, "question", side_effect=_fail_on_dialog("QMessageBox.question")),
        patch.object(
            QFileDialog,
            "getOpenFileName",
            side_effect=_fail_on_dialog("QFileDialog.getOpenFileName"),
        ),
        patch.object(
            QFileDialog,
            "getOpenFileNames",
            side_effect=_fail_on_dialog("QFileDialog.getOpenFileNames"),
        ),
        patch.object(
            QFileDialog,
            "getSaveFileName",
            side_effect=_fail_on_dialog("QFileDialog.getSaveFileName"),
        ),
        patch.object(
            QFileDialog,
            "getExistingDirectory",
            side_effect=_fail_on_dialog("QFileDialog.getExistingDirectory"),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def fs_tools_translations() -> Iterator[None]:
    """Point the shared translator at the fs_tools catalog for the duration of a test.

    fs_tools ships its own self-contained translation catalog; its windows use
    keys (tools_window, catalog_builder, ...) that no longer exist in the main
    foxhole_stockpiles catalog. This mirrors what ``fs_tools.gui._bootstrap`` does
    at runtime, and restores the default afterwards so main-app tests are unaffected.

    Yields:
        None: Control to the test while the fs_tools catalog is active.
    """
    set_translations_resource(_TOOLS_TRANSLATIONS)
    get_translator("en")
    try:
        yield
    finally:
        set_translations_resource(_MAIN_TRANSLATIONS)
        get_translator("en")
