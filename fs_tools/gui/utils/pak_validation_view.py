"""The window members that the PAK validation controller works with."""

from typing import Protocol

from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QPushButton


class PakValidationView(Protocol):
    """What a window must offer for its selected PAK files to be validated."""

    mod_pak_files: list[str]
    vanilla_pak_file: str | None
    vanilla_group: QGroupBox
    vanilla_info: QLabel
    vanilla_browse_button: QPushButton
    vanilla_clear_button: QPushButton
    add_mod_pak_button: QPushButton
    remove_mod_pak_button: QPushButton
    clear_mod_pak_button: QPushButton
    mod_pak_list_widget: QListWidget
    start_button: QPushButton

    def set_validation_status(self, text: str, color: str) -> None:
        """Show a validation status message.

        Args:
            text (str): The message.
            color (str): The message's CSS color.
        """
        ...

    def clear_vanilla_pak(self) -> None:
        """Clear the vanilla PAK file selection."""
        ...
