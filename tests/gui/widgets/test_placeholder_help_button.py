"""The button that lists the placeholders of a field."""

from typing import Any
from unittest.mock import patch

from PySide6.QtCore import Qt

from foxhole_stockpiles.gui.widgets import placeholder_help_button as mod
from foxhole_stockpiles.gui.widgets.config_tabs.output_handler_dialog import OutputHandlerDialog
from foxhole_stockpiles.gui.widgets.placeholder_help_button import PlaceholderHelpButton
from foxhole_stockpiles.i18n import t


def test_the_list_shows_on_hover(qtbot: Any) -> None:
    """As the tooltip of the button."""
    button = PlaceholderHelpButton()
    qtbot.addWidget(button)

    assert button.text() == "?"
    assert "{name}" in button.toolTip()
    assert button.toolTip() == t("output_tab.handler_dialog.placeholder_help")


def test_the_list_shows_on_a_click_too(qtbot: Any) -> None:
    """Nobody has to find a tooltip to read it."""
    button = PlaceholderHelpButton()
    qtbot.addWidget(button)

    with patch.object(mod.QToolTip, "showText") as show:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    show.assert_called_once()
    assert show.call_args.args[1] == button.toolTip()


def test_every_field_with_placeholders_has_one(qtbot: Any) -> None:
    """The file path, the image path and the Discord message."""
    dialog = OutputHandlerDialog()
    qtbot.addWidget(dialog)

    buttons = [
        dialog.file_path_help,
        dialog.image_group.path_help,
        dialog.discord_group.message_help,
    ]

    assert all(isinstance(button, PlaceholderHelpButton) for button in buttons)
