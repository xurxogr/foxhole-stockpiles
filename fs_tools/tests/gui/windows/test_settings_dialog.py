"""Tests for SettingsDialog."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.i18n import t
from fs_tools.gui.windows.settings_dialog import SettingsDialog


@pytest.fixture
def dialog(qtbot: Any) -> SettingsDialog:
    """Create a SettingsDialog instance.

    Args:
        qtbot: pytest-qt fixture.

    Returns:
        SettingsDialog: Dialog instance.
    """
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = AppSettings()
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        return dialog


def test_dialog_initialization(dialog: SettingsDialog) -> None:
    """The dialog exposes its sections and config manager.

    Args:
        dialog (SettingsDialog): Dialog instance.
    """
    assert t("settings_dialog.title") in dialog.windowTitle()
    assert dialog.database_path_input is not None
    assert dialog.external_tools_tab is not None
    assert dialog.db_builder_tab is not None
    assert dialog.config_manager is not None


def test_database_download_button_visible_only_when_db_unset(dialog: SettingsDialog) -> None:
    """The DB download button shows when no database path is set and hides when one is.

    Args:
        dialog (SettingsDialog): Dialog instance.
    """
    dialog.database_path_input.setText("")
    assert not dialog.database_download_btn.isHidden()

    dialog.database_path_input.setText("/tmp/db.h5")
    assert dialog.database_download_btn.isHidden()


def test_load_current_settings_populates_database_path(qtbot: Any) -> None:
    """The configured database path is loaded into the input.

    Args:
        qtbot: pytest-qt fixture.
    """
    settings = AppSettings()
    settings = settings.model_copy(
        update={"scanner": settings.scanner.model_copy(update={"database_path": Path("/db.h5")})}
    )

    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = settings
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.database_path_input.text() == str(Path("/db.h5"))


def test_save_and_accept_persists_database_path(qtbot: Any) -> None:
    """Saving writes the scanner database path to the config.

    Args:
        qtbot: pytest-qt fixture.
    """
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = AppSettings()
        with patch("fs_tools.gui.windows.settings_dialog.ConfigManager") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.save_config.return_value = (True, "Success")

            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            dialog.database_path_input.setText("/new/db.h5")

            dialog._save_and_accept()

            mock_config.save_config.assert_called_once()
            saved_settings = mock_config.save_config.call_args[0][0]
            assert saved_settings.scanner.database_path == Path("/new/db.h5")


def test_save_and_accept_empty_database_path_is_none(qtbot: Any) -> None:
    """An empty database path is persisted as None.

    Args:
        qtbot: pytest-qt fixture.
    """
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = AppSettings()
        with patch("fs_tools.gui.windows.settings_dialog.ConfigManager") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.save_config.return_value = (True, "Success")

            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            dialog.database_path_input.setText("")

            dialog._save_and_accept()

            saved_settings = mock_config.save_config.call_args[0][0]
            assert saved_settings.scanner.database_path is None


def test_load_current_settings_selects_language(qtbot: Any) -> None:
    """The configured language is preselected in the combo.

    Args:
        qtbot: pytest-qt fixture.
    """
    settings = AppSettings()
    settings = settings.model_copy(
        update={"gui": settings.gui.model_copy(update={"language": "es"})}
    )

    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = settings
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)

        assert dialog.language_input.currentData() == "es"


def test_save_and_accept_persists_and_applies_language(qtbot: Any) -> None:
    """Saving a changed language persists it and applies it live.

    Args:
        qtbot: pytest-qt fixture.
    """
    base = AppSettings()
    spanish_settings = base.model_copy(
        update={"gui": base.gui.model_copy(update={"language": "es"})}
    )
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = spanish_settings  # start from "es" so "en" is a change
        with patch("fs_tools.gui.windows.settings_dialog.ConfigManager") as mock_config_class:
            with patch("fs_tools.gui.windows.settings_dialog.set_language") as mock_set_language:
                mock_config = mock_config_class.return_value
                mock_config.save_config.return_value = (True, "Success")

                dialog = SettingsDialog()
                qtbot.addWidget(dialog)
                en_index = dialog.language_input.findData("en")
                dialog.language_input.setCurrentIndex(en_index)

                dialog._save_and_accept()

                saved_settings = mock_config.save_config.call_args[0][0]
                assert saved_settings.gui.language == "en"
                mock_set_language.assert_called_once_with("en")


def test_save_and_accept_unchanged_language_not_reapplied(qtbot: Any) -> None:
    """Saving without changing language does not re-apply it.

    Args:
        qtbot: pytest-qt fixture.
    """
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = AppSettings()  # default language "en"
        with patch("fs_tools.gui.windows.settings_dialog.ConfigManager") as mock_config_class:
            with patch("fs_tools.gui.windows.settings_dialog.set_language") as mock_set_language:
                mock_config = mock_config_class.return_value
                mock_config.save_config.return_value = (True, "Success")

                dialog = SettingsDialog()
                qtbot.addWidget(dialog)

                dialog._save_and_accept()

                mock_set_language.assert_not_called()


def test_save_and_accept_failure_shows_status(qtbot: Any) -> None:
    """A save failure surfaces the message in the status label.

    Args:
        qtbot: pytest-qt fixture.
    """
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = AppSettings()
        with patch("fs_tools.gui.windows.settings_dialog.ConfigManager") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.save_config.return_value = (False, "Save failed")

            dialog = SettingsDialog()
            qtbot.addWidget(dialog)

            dialog._save_and_accept()

            assert "Save failed" in dialog.status_label.text()
            assert not dialog.status_label.isHidden()


def test_save_and_accept_exception_shows_status(qtbot: Any) -> None:
    """An exception during save surfaces the error in the status label.

    Args:
        qtbot: pytest-qt fixture.
    """
    with patch("fs_tools.gui.windows.settings_dialog.get_settings") as mock_get_settings:
        mock_get_settings.return_value = AppSettings()
        with patch("fs_tools.gui.windows.settings_dialog.ConfigManager") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.save_config.side_effect = Exception("Test error")

            dialog = SettingsDialog()
            qtbot.addWidget(dialog)

            dialog._save_and_accept()

            assert "Test error" in dialog.status_label.text()
            assert not dialog.status_label.isHidden()


def test_show_event_fits_height_once(dialog: SettingsDialog) -> None:
    """The first show fits the dialog height; later shows do not re-fit."""
    from PySide6.QtGui import QShowEvent

    assert dialog._height_fitted is False
    dialog.showEvent(QShowEvent())
    assert dialog._height_fitted is True
    dialog.showEvent(QShowEvent())  # second show is a no-op for fitting


_FILE_DIALOG = "fs_tools.gui.windows.settings_dialog.QFileDialog.getOpenFileName"


def test_browse_database_sets_path(dialog: SettingsDialog) -> None:
    """Browsing selects a database file into the path input."""
    with patch(_FILE_DIALOG, return_value=("/db/templates.h5", "")):
        dialog._browse_database()
    assert dialog.database_path_input.text() == "/db/templates.h5"


def test_browse_database_cancelled(dialog: SettingsDialog) -> None:
    """Cancelling the browse dialog leaves the path unchanged."""
    dialog.database_path_input.setText("keep.h5")
    with patch(_FILE_DIALOG, return_value=("", "")):
        dialog._browse_database()
    assert dialog.database_path_input.text() == "keep.h5"


def test_language_change_retranslates(dialog: SettingsDialog) -> None:
    """A language change re-applies the dialog's translatable strings."""
    dialog._on_language_changed("en")
    assert dialog.language_label.text() != ""
