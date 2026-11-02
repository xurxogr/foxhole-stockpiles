"""Controller that checks the selected PAK files against the catalog in the background."""

from fs_assets.types import PakCoverage
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox, QWidget

from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.i18n import t
from fs_tools.gui.utils.pak_coverage_status import (
    covers_all_overlays,
    has_catalog_icons,
    missing_overlays,
)
from fs_tools.gui.utils.pak_coverage_worker import PakCoverageWorker
from fs_tools.gui.utils.pak_validation_view import PakValidationView

STATUS_COLOR_PROGRESS = "#2196F3"
STATUS_COLOR_SUCCESS = "#4CAF50"
STATUS_COLOR_WARNING = "#FF9800"
STATUS_COLOR_ERROR = "#F44336"


class PakValidationController(QObject):
    """Runs the mod and vanilla PAK checks and reflects their outcome in the view."""

    def __init__(self, view: PakValidationView, settings: AppSettings, parent: QWidget) -> None:
        """Initialize the controller.

        Args:
            view (PakValidationView): The window showing the PAK files and the outcome.
            settings (AppSettings): Settings holding the catalog file.
            parent (QWidget): Parent of the workers and of the warning dialogs.
        """
        super().__init__(parent)
        self._view = view
        self._settings = settings
        self._parent_widget = parent

        self.validation_worker: PakCoverageWorker | None = None
        self.validation_result: PakCoverage | None = None
        self.validation_failed = False
        self.is_validating = False

        self.vanilla_validation_worker: PakCoverageWorker | None = None
        self.vanilla_validation_result: PakCoverage | None = None
        self.is_validating_vanilla = False

    def trigger_validation(self) -> None:
        """Check in a background thread which catalog icons the mod PAK files contain."""
        view = self._view
        if not view.mod_pak_files:
            return

        # Let any previous check finish before starting a new one
        if self.validation_worker and self.validation_worker.isRunning():
            self.validation_worker.wait()

        catalog_path = self._settings.database_builder.catalog_file
        if not catalog_path:
            return

        self._set_pak_controls_enabled(False)
        self.is_validating = True
        self.validation_failed = False
        view.set_validation_status(
            text=t("database_builder.validation.validating_pak"), color=STATUS_COLOR_PROGRESS
        )
        self.update_start_button_state()

        self.validation_worker = PakCoverageWorker(
            catalog_path=catalog_path,
            pak_files=view.mod_pak_files.copy(),
            parent=self._parent_widget,
        )
        self.validation_worker.coverage_ready.connect(self._on_validation_complete)
        self.validation_worker.failed.connect(self._on_validation_failed)
        self.validation_worker.start()

    def _on_validation_complete(self, result: PakCoverage) -> None:
        """Handle the coverage report of the mod PAK files.

        Args:
            result (PakCoverage): Which catalog icons the mod PAK files contain.
        """
        view = self._view
        self.is_validating = False
        self.validation_result = result
        self._set_pak_controls_enabled(True)

        if not has_catalog_icons(result):
            # Nothing to import: none of the catalog's icons are in these files
            view.set_validation_status(
                text=t("database_builder.validation.no_catalog_icons"), color=STATUS_COLOR_ERROR
            )
            view.vanilla_group.setVisible(False)
        elif covers_all_overlays(result):
            view.set_validation_status(
                text=t("database_builder.validation.all_assets_found"), color=STATUS_COLOR_SUCCESS
            )
            view.vanilla_group.setVisible(False)
            view.clear_vanilla_pak()
        else:
            view.set_validation_status(
                text=t("database_builder.validation.missing_assets"), color=STATUS_COLOR_WARNING
            )
            view.vanilla_group.setVisible(True)
            view.vanilla_info.setText(
                t(
                    "database_builder.vanilla_warning_missing",
                    missing=" and ".join(missing_overlays(result)),
                )
            )

        self.update_start_button_state()

    def _on_validation_failed(self, error_msg: str) -> None:
        """Handle a mod PAK check that could not run (e.g. an unreadable file).

        Args:
            error_msg (str): The error message.
        """
        view = self._view
        self.is_validating = False
        self.validation_result = None
        self.validation_failed = True
        self._set_pak_controls_enabled(True)
        view.set_validation_status(
            text=t("database_builder.validation.check_failed", error=error_msg),
            color=STATUS_COLOR_ERROR,
        )
        view.vanilla_group.setVisible(False)
        self.update_start_button_state()

    def _set_pak_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable PAK file controls.

        Args:
            enabled (bool): Whether to enable or disable controls.
        """
        view = self._view
        view.add_mod_pak_button.setEnabled(enabled)
        view.remove_mod_pak_button.setEnabled(enabled)
        view.clear_mod_pak_button.setEnabled(enabled)
        view.mod_pak_list_widget.setAcceptDrops(enabled)

    def trigger_vanilla_validation(self) -> None:
        """Check in a background thread that the vanilla PAK has every overlay."""
        view = self._view
        if not view.vanilla_pak_file:
            return

        catalog_path = self._settings.database_builder.catalog_file
        if not catalog_path:
            return

        self._set_vanilla_controls_enabled(False)
        self.is_validating_vanilla = True
        view.set_validation_status(
            text=t("database_builder.validation.validating_vanilla"), color=STATUS_COLOR_PROGRESS
        )
        self.update_start_button_state()

        self.vanilla_validation_worker = PakCoverageWorker(
            catalog_path=catalog_path,
            pak_files=[view.vanilla_pak_file],
            parent=self._parent_widget,
        )
        self.vanilla_validation_worker.coverage_ready.connect(self._on_vanilla_validation_complete)
        self.vanilla_validation_worker.failed.connect(self._on_vanilla_validation_failed)
        self.vanilla_validation_worker.start()

    def _on_vanilla_validation_complete(self, result: PakCoverage) -> None:
        """Handle the coverage report of the vanilla PAK file.

        Args:
            result (PakCoverage): Which catalog icons the vanilla PAK contains.
        """
        self.is_validating_vanilla = False
        self.vanilla_validation_result = result
        self._set_vanilla_controls_enabled(True)

        if covers_all_overlays(result):
            self._view.vanilla_info.setVisible(False)
            self._view.set_validation_status(
                text=t("database_builder.validation.all_assets_found"), color=STATUS_COLOR_SUCCESS
            )
        else:
            self._show_invalid_vanilla(" and ".join(missing_overlays(result)))

        self.update_start_button_state()

    def _on_vanilla_validation_failed(self, error_msg: str) -> None:
        """Handle a vanilla PAK check that could not run.

        Args:
            error_msg (str): The error message.
        """
        self.is_validating_vanilla = False
        self.vanilla_validation_result = None
        self._set_vanilla_controls_enabled(True)
        self._show_invalid_vanilla(error_msg)
        self.update_start_button_state()

    def _show_invalid_vanilla(self, reason: str) -> None:
        """Flag the selected vanilla PAK as unusable.

        Args:
            reason (str): What is missing, or why it could not be checked.
        """
        self._view.vanilla_info.setVisible(True)
        self._view.set_validation_status(
            text=t("database_builder.validation.invalid_vanilla"), color=STATUS_COLOR_ERROR
        )
        QMessageBox.warning(
            self._parent_widget,
            t("database_builder.invalid_vanilla_title"),
            t("database_builder.invalid_vanilla_message", missing=reason),
        )

    def _set_vanilla_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable vanilla PAK file controls.

        Args:
            enabled (bool): Whether to enable or disable controls.
        """
        self._view.vanilla_browse_button.setEnabled(enabled)
        self._view.vanilla_clear_button.setEnabled(enabled)

    def mod_needs_vanilla(self) -> bool:
        """Return whether the mod PAK files have catalog icons but lack overlays.

        Returns:
            bool: True if the vanilla PAK is needed for the missing overlays.
        """
        result = self.validation_result
        return bool(result and has_catalog_icons(result) and not covers_all_overlays(result))

    def vanilla_is_valid(self) -> bool:
        """Return whether the vanilla PAK was checked and has every overlay.

        Returns:
            bool: True if the vanilla PAK can supply the missing overlays.
        """
        result = self.vanilla_validation_result
        return bool(result and covers_all_overlays(result))

    def update_start_button_state(self) -> None:
        """Update the start button enabled state based on validation results.

        The start button is disabled when:
        - Validation is in progress (mod or vanilla)
        - The mod PAK files could not be checked or hold no catalog icon
        - The mod PAK files lack overlays and no valid vanilla PAK is selected
        """
        start_button = self._view.start_button
        if self.is_validating or self.is_validating_vanilla:
            start_button.setEnabled(False)
            return

        # If no mod PAK files selected, enable (will be caught by validate_inputs)
        if not self._view.mod_pak_files:
            start_button.setEnabled(True)
            return

        if self.validation_failed:
            start_button.setEnabled(False)
            return

        result = self.validation_result
        if result is None:
            # Not checked yet
            start_button.setEnabled(True)
        elif not has_catalog_icons(result):
            start_button.setEnabled(False)
        elif covers_all_overlays(result):
            start_button.setEnabled(True)
        else:
            start_button.setEnabled(self.vanilla_is_valid())

    def wait_for_workers(self) -> None:
        """Block until any running PAK check has finished."""
        if self.validation_worker and self.validation_worker.isRunning():
            self.validation_worker.wait()
        if self.vanilla_validation_worker and self.vanilla_validation_worker.isRunning():
            self.vanilla_validation_worker.wait()
