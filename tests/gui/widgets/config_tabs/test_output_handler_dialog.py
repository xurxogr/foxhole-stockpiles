"""Tests for the Google Sheets validation of OutputHandlerDialog."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections import (
    FileHandlerSettings,
    ImageHandlerSettings,
    OutputHandlerConfig,
    SheetsHandlerSettings,
)
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType
from foxhole_stockpiles.gui.widgets.config_tabs import output_handler_dialog as dialog_mod
from foxhole_stockpiles.gui.widgets.config_tabs.output_handler_dialog import OutputHandlerDialog

_URL = "https://docs.google.com/spreadsheets/d/ABC-123"


@pytest.fixture
def dialog(qtbot: Any, tmp_path: Path) -> OutputHandlerDialog:
    """Build a dialog holding a valid Google Sheets configuration.

    Args:
        qtbot (Any): PyQt test fixture.
        tmp_path (Path): Directory for the credentials file.

    Returns:
        OutputHandlerDialog: The dialog.
    """
    credentials = tmp_path / "credentials.json"
    credentials.write_text("{}", encoding="utf-8")
    widget = OutputHandlerDialog()
    qtbot.addWidget(widget)
    widget.name_input.setText("sheets")
    widget.handler_type_input.setCurrentText(OutputHandlerType.SHEETS.value)
    widget.creds_path_input.setText(str(credentials))
    widget.spreadsheet_url_input.setText(_URL)
    widget.sheet_id_input.setText("Sheet1")
    widget.start_cell_input.setText("A1")
    widget.row_format_input.setText("{code}")
    return widget


def test_invalid_credentials_path_focuses_the_credentials_field(
    dialog: OutputHandlerDialog,
) -> None:
    """The warning about the credentials path leads the user to that field.

    Args:
        dialog (OutputHandlerDialog): The dialog.
    """
    dialog.creds_path_input.setText("/does/not/exist.json")

    with (
        patch.object(dialog_mod.QMessageBox, "warning") as warning,
        patch.object(dialog.creds_path_input, "setFocus") as focus,
        patch.object(dialog, "accept") as accept,
    ):
        dialog._validate_and_accept()

    warning.assert_called_once()
    focus.assert_called_once_with()
    accept.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [_URL, f"{_URL}/", f"{_URL}/edit?gid=0#gid=0"],
    ids=["no-trailing-slash", "trailing-slash", "edit-link"],
)
def test_spreadsheet_links_the_handler_can_use_are_accepted(
    dialog: OutputHandlerDialog, url: str
) -> None:
    """The dialog accepts every link form the handler can get an ID from.

    Args:
        dialog (OutputHandlerDialog): The dialog.
        url (str): The link under test.
    """
    dialog.spreadsheet_url_input.setText(url)

    with (
        patch.object(dialog_mod.QMessageBox, "warning") as warning,
        patch.object(dialog, "accept") as accept,
    ):
        dialog._validate_and_accept()

    warning.assert_not_called()
    accept.assert_called_once_with()


def test_link_to_another_site_is_rejected(dialog: OutputHandlerDialog) -> None:
    """A link that only resembles a spreadsheet link is refused and focused.

    Args:
        dialog (OutputHandlerDialog): The dialog.
    """
    dialog.spreadsheet_url_input.setText("https://docs.google.com.example.org/spreadsheets/d/x/")

    with (
        patch.object(dialog_mod.QMessageBox, "warning") as warning,
        patch.object(dialog.spreadsheet_url_input, "setFocus") as focus,
        patch.object(dialog, "accept") as accept,
    ):
        dialog._validate_and_accept()

    warning.assert_called_once()
    focus.assert_called_once_with()
    accept.assert_not_called()


def test_pasted_whitespace_is_not_saved(dialog: OutputHandlerDialog) -> None:
    """A link accepted with surrounding spaces is saved in the form the handler reads.

    Args:
        dialog (OutputHandlerDialog): The dialog.
    """
    dialog.spreadsheet_url_input.setText(f"  {_URL}/  ")

    with (
        patch.object(dialog_mod.QMessageBox, "warning") as warning,
        patch.object(dialog, "accept") as accept,
    ):
        dialog._validate_and_accept()

    warning.assert_not_called()
    accept.assert_called_once_with()
    handler = dialog.get_handler_config().handler
    assert isinstance(handler, SheetsHandlerSettings)
    assert handler.spreadsheet_url == f"{_URL}/"


@pytest.mark.parametrize(
    ("handler_type", "name"),
    [
        (OutputHandlerType.FILE, "File Output"),
        (OutputHandlerType.WEBHOOK, "Webhook"),
        (OutputHandlerType.CONSOLE, "Console"),
        (OutputHandlerType.SHEETS, "Append rows (Google Sheets)"),
        (OutputHandlerType.RETURN, "API Response"),
    ],
)
def test_a_handler_left_unnamed_gets_the_name_of_its_type(
    dialog: OutputHandlerDialog, handler_type: OutputHandlerType, name: str
) -> None:
    """Leaving the name empty is allowed."""
    dialog.name_input.clear()
    dialog.handler_type_input.setCurrentText(handler_type.value)

    assert dialog.get_handler_config().name == name


def test_a_file_handler_left_without_path_writes_to_the_default_one(
    dialog: OutputHandlerDialog,
) -> None:
    """The extension of the default path comes from the format."""
    dialog.file_path_input.clear()
    dialog.handler_type_input.setCurrentText(OutputHandlerType.FILE.value)

    handler = dialog.get_handler_config().handler

    assert isinstance(handler, FileHandlerSettings)
    assert handler.path == "output"


@pytest.mark.parametrize(
    ("selected", "output_format"),
    [("json", OutputFormat.JSON), ("csv", OutputFormat.CSV), ("tsv", OutputFormat.TSV)],
)
def test_the_selected_format_survives_saving_and_loading(
    dialog: OutputHandlerDialog, selected: str, output_format: OutputFormat
) -> None:
    """What the dialog saves, it shows again; only a file handler has formats to choose."""
    dialog.handler_type_input.setCurrentText(OutputHandlerType.FILE.value)
    dialog.format_input.setCurrentText(selected)
    config = dialog.get_handler_config()
    assert config.format.type == output_format

    dialog.format_input.setCurrentText("json")
    dialog.load_handler(config)

    assert dialog.format_input.currentText() == selected


class TestImageHandler:
    """The fields of the handler that saves stockpiles as images."""

    @pytest.fixture
    def image_dialog(self, qtbot: Any) -> OutputHandlerDialog:
        """Build a dialog set to the image handler.

        Args:
            qtbot (Any): PyQt test fixture.

        Returns:
            OutputHandlerDialog: The dialog.
        """
        widget = OutputHandlerDialog()
        qtbot.addWidget(widget)
        widget.handler_type_input.setCurrentText(OutputHandlerType.IMAGE.value)
        return widget

    def test_only_its_fields_are_shown(self, image_dialog: OutputHandlerDialog) -> None:
        """The other handlers keep theirs hidden, as does the output format."""
        assert not image_dialog.image_group.isHidden()
        assert image_dialog.file_group.isHidden()
        assert image_dialog.format_input.isHidden()

    def test_values_become_its_settings(self, image_dialog: OutputHandlerDialog) -> None:
        """What is typed ends up in the configuration."""
        image_dialog.image_group.path_input.setText("out/{stockpile_name}.png")
        image_dialog.image_group.appearance.headline_input.setText("Report {name}")
        image_dialog.image_group.appearance.icon_mod_input.setCurrentText("mymod")

        handler = image_dialog.get_handler_config().handler

        assert isinstance(handler, ImageHandlerSettings)
        assert handler.path == "out/{stockpile_name}.png"
        assert handler.headline == "Report {name}"
        assert handler.icon_mod == "mymod"
        assert handler.font_path is None

    def test_settings_are_shown_when_editing(self, qtbot: Any) -> None:
        """An existing handler can be changed."""
        config = OutputHandlerConfig(
            name="image",
            handler=ImageHandlerSettings(path="a.png", icon_mod="mymod", font_path="f.ttf"),
        )
        widget = OutputHandlerDialog(handler_config=config)
        qtbot.addWidget(widget)

        assert widget.image_group.path_input.text() == "a.png"
        assert widget.image_group.appearance.icon_mod_input.currentText() == "mymod"
        assert widget.image_group.appearance.font_path_input.text() == "f.ttf"

    def test_path_is_required(self, image_dialog: OutputHandlerDialog) -> None:
        """Without it the dialog stays open and says why."""
        image_dialog.image_group.path_input.setText("  ")
        with patch.object(dialog_mod.QMessageBox, "warning") as warning:
            image_dialog._validate_and_accept()

        warning.assert_called_once()

    def test_mods_of_the_database_are_offered(self, qtbot: Any) -> None:
        """They come from the template database of the scanner."""
        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.image_appearance_fields.list_icon_mods",
            return_value=["mymod", "vanilla"],
        ):
            widget = OutputHandlerDialog()
        qtbot.addWidget(widget)
        combo = widget.image_group.appearance.icon_mod_input

        assert [combo.itemText(index) for index in range(combo.count())] == ["mymod", "vanilla"]
        assert combo.currentText() == "vanilla"


def test_image_handler_can_merge_stockpiles(qtbot: Any) -> None:
    """The setting is shown when editing and read back."""
    config = OutputHandlerConfig(
        name="image", handler=ImageHandlerSettings(path="a.png", aggregate=True)
    )
    widget = OutputHandlerDialog(handler_config=config)
    qtbot.addWidget(widget)
    aggregate_input = widget.image_group.appearance.aggregate_input

    assert aggregate_input.isChecked()
    aggregate_input.setChecked(False)
    handler = widget.get_handler_config().handler
    assert isinstance(handler, ImageHandlerSettings)
    assert handler.aggregate is False
