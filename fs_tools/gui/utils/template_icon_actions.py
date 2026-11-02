"""Save, replace and delete actions for the template icon selected in a window."""

import logging
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from foxhole_stockpiles.core.image_io import write_bgr
from foxhole_stockpiles.i18n import t
from fs_tools.core.template_store import delete_icon, replace_icon
from fs_tools.gui.utils.template_icon_view import TemplateIconView

logger = logging.getLogger(__name__)


class TemplateIconActions:
    """Runs the icon actions on the view's selected template, asking the user as needed."""

    def __init__(self, view: TemplateIconView, parent: QWidget) -> None:
        """Initialize the actions.

        Args:
            view (TemplateIconView): The window holding the selection and the database.
            parent (QWidget): Parent of the dialogs.
        """
        self._view = view
        self._parent = parent

    def on_replace_icon(self) -> None:
        """Handle replace icon button click."""
        view = self._view
        if not view.selected_template or not view.current_resolution or not view.database_path:
            return

        _idx, template = view.selected_template

        file_path, _ = QFileDialog.getOpenFileName(
            self._parent,
            t("database_visualizer.select_replacement_icon"),
            "",
            "PNG Files (*.png);;All Files (*)",
        )

        if not file_path:
            return

        # The icon is resized and composited like templates built from the game
        try:
            replace_icon(Path(view.database_path), template, Path(file_path))
        except Exception as e:  # noqa: BLE001 - surface any replace failure to the user
            self._show_replace_error(str(e))
            return

        view.reload_current_resolution()

        QMessageBox.information(
            self._parent,
            t("database_visualizer.replace_success_title"),
            t("database_visualizer.replace_success_message").replace("{code}", template.code),
        )

    def on_save_icon(self) -> None:
        """Handle save icon button click."""
        if not self._view.selected_template:
            return

        _idx, template = self._view.selected_template

        crated_suffix = "_crated" if template.crated else ""
        default_name = f"{template.code}{crated_suffix}_{template.resolution.value}p.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self._parent,
            t("database_visualizer.save_icon_dialog"),
            default_name,
            "PNG Files (*.png);;All Files (*)",
        )

        if not file_path:
            return

        try:
            write_bgr(file_path, template.image)
        except Exception as e:  # noqa: BLE001 - surface any save failure to the user
            logger.exception("Failed to save icon")
            QMessageBox.critical(
                self._parent,
                t("database_visualizer.save_error_title"),
                t("database_visualizer.save_error_message").replace("{error}", str(e)),
            )
            return

        QMessageBox.information(
            self._parent,
            t("database_visualizer.save_success_title"),
            t("database_visualizer.save_success_message").replace("{path}", file_path),
        )

    def on_delete_icon(self) -> None:
        """Handle delete icon button click."""
        view = self._view
        if not view.selected_template or not view.current_resolution or not view.database_path:
            return

        _idx, template = view.selected_template

        reply = QMessageBox.question(
            self._parent,
            t("database_visualizer.delete_confirm_title"),
            t("database_visualizer.delete_confirm_message")
            .replace("{code}", template.code)
            .replace("{resolution}", view.current_resolution.value),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_icon(Path(view.database_path), template)
        except Exception as e:  # noqa: BLE001 - surface any delete failure to the user
            logger.exception("Failed to delete icon")
            QMessageBox.critical(
                self._parent,
                t("database_visualizer.delete_error_title"),
                t("database_visualizer.delete_error_message").replace("{error}", str(e)),
            )
            return

        QMessageBox.information(
            self._parent,
            t("database_visualizer.delete_success_title"),
            t("database_visualizer.delete_success_message").replace("{code}", template.code),
        )

        view.clear_selection()
        view.reload_current_resolution()

    def _show_replace_error(self, error: str) -> None:
        """Show error message for failed icon replacement.

        Args:
            error (str): Error message to display.
        """
        logger.exception("Failed to replace icon")
        QMessageBox.critical(
            self._parent,
            t("database_visualizer.replace_error_title"),
            t("database_visualizer.replace_error_message").replace("{error}", error),
        )
