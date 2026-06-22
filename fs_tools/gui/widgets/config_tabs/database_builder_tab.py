"""Database Builder settings tab."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.database_builder import DatabaseBuilderSettings
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class DatabaseBuilderTab(QWidget):
    """Tab for Database Builder configuration.

    Note: External tools (repak, umodel) are configured in ExternalToolsTab.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the Database Builder tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        # The worker count is no longer edited here (it is chosen per-build in
        # the build-database window and via the CLI ``--workers`` flag). The
        # configured value is preserved across a save so those defaults survive.
        self._workers: int | None = None
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Files and Settings Group
        self.settings_group = QGroupBox()
        settings_layout = QFormLayout()
        self.settings_group.setLayout(settings_layout)

        # Catalog file
        self.catalog_label = QLabel()
        catalog_layout = QHBoxLayout()
        self.catalog_file_input = QLineEdit()
        self.catalog_file_input.textChanged.connect(self._update_download_buttons)
        catalog_layout.addWidget(self.catalog_file_input)
        self.catalog_download_btn = QPushButton()
        self.catalog_download_btn.setMaximumWidth(80)
        self.catalog_download_btn.clicked.connect(
            lambda: self._open_url("https://github.com/xurxogr/foxhole-stockpiles/tree/main/data")
        )
        catalog_layout.addWidget(self.catalog_download_btn)
        self.catalog_browse_btn = QPushButton()
        self.catalog_browse_btn.clicked.connect(self.browse_catalog_file)
        catalog_layout.addWidget(self.catalog_browse_btn)
        settings_layout.addRow(self.catalog_label, catalog_layout)

        layout.addWidget(self.settings_group)

        # Resolutions Group
        self.resolutions_group = QGroupBox()
        resolutions_layout = QVBoxLayout()
        self.resolutions_group.setLayout(resolutions_layout)

        self.resolutions_info = QLabel()
        self.resolutions_info.setWordWrap(True)
        resolutions_layout.addWidget(self.resolutions_info)

        self.resolution_list = QListWidget()
        # Shows several resolutions at once; the list scrolls for the rest.
        self.resolution_list.setMaximumHeight(120)

        # Add "All" option first (will be translated in retranslate)
        all_item = self.resolution_list.addItem("")
        if all_item is None:
            all_item = self.resolution_list.item(0)
        if all_item:
            all_item.setFlags(all_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            all_item.setCheckState(Qt.CheckState.Checked)  # Default to all
            all_item.setData(Qt.ItemDataRole.UserRole, "all")

        # Add individual resolutions
        for resolution in SupportedResolution:
            item = self.resolution_list.addItem(resolution.value)
            if item is None:
                item = self.resolution_list.item(self.resolution_list.count() - 1)
            if item:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)  # Default to all
                item.setData(Qt.ItemDataRole.UserRole, resolution.value)

        self.resolution_list.itemChanged.connect(self._handle_resolution_selection)
        resolutions_layout.addWidget(self.resolution_list)

        layout.addWidget(self.resolutions_group)

        # Status info
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "QLabel { background-color: palette(alternate-base); padding: 8px; "
            "border: 2px solid #FF9800; margin-top: 10px; }"
        )
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Apply translations
        self.retranslate()

        # Initial update of download button visibility
        self._update_download_buttons()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.settings_group.setTitle(t("database_builder_tab.settings_group"))

        self.catalog_label.setText(t("database_builder_tab.catalog_file"))
        self.catalog_label.setToolTip(t("database_builder_tab.catalog_tooltip"))
        self.catalog_file_input.setPlaceholderText(t("database_builder_tab.catalog_placeholder"))
        self.catalog_download_btn.setText(t("external_tools_tab.download"))
        self.catalog_browse_btn.setText(t("common.browse"))

        self.resolutions_group.setTitle(t("database_builder_tab.resolutions_group"))
        self.resolutions_info.setText(t("database_builder_tab.resolutions_info"))

        # Update "All Resolutions" item
        all_item = self.resolution_list.item(0)
        if all_item:
            all_item.setText(t("database_builder_tab.all_resolutions"))

        self.status_label.setText(t("database_builder_tab.status_note"))

    def _update_download_buttons(self) -> None:
        """Update visibility of download buttons based on whether fields are empty."""
        self.catalog_download_btn.setVisible(not self.catalog_file_input.text().strip())

    def _open_url(self, url: str) -> None:
        """Open URL in default browser.

        Args:
            url (str): URL to open
        """
        QDesktopServices.openUrl(QUrl(url))

    def browse_catalog_file(self) -> None:
        """Open file dialog to select catalog file (catalog.json)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("database_builder_tab.select_catalog"),
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.catalog_file_input.setText(file_path)

    def _handle_resolution_selection(self, item: object) -> None:
        """Handle resolution selection changes in the list.

        Args:
            item (object): The list item that changed
        """
        if not hasattr(item, "data") or not hasattr(item, "checkState"):
            return

        # Temporarily disconnect to avoid recursion
        self.resolution_list.itemChanged.disconnect(self._handle_resolution_selection)

        try:
            item_data = item.data(Qt.ItemDataRole.UserRole)
            is_checked = item.checkState() == Qt.CheckState.Checked

            if item_data == "all":
                # Check/uncheck all items
                for i in range(self.resolution_list.count()):
                    list_item = self.resolution_list.item(i)
                    if list_item:
                        list_item.setCheckState(
                            Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
                        )
            else:
                # Check if all individual items are now checked
                all_checked = True
                for i in range(1, self.resolution_list.count()):  # Skip "All" item at index 0
                    list_item = self.resolution_list.item(i)
                    if list_item and list_item.checkState() != Qt.CheckState.Checked:
                        all_checked = False
                        break

                # Update "All" checkbox accordingly
                all_item = self.resolution_list.item(0)
                if all_item:
                    all_item.setCheckState(
                        Qt.CheckState.Checked if all_checked else Qt.CheckState.Unchecked
                    )

        finally:
            # Reconnect
            self.resolution_list.itemChanged.connect(self._handle_resolution_selection)

    def set_values(self, settings: DatabaseBuilderSettings) -> None:
        """Set widget values from settings.

        Args:
            settings (DatabaseBuilderSettings): DatabaseBuilderSettings instance to load
                values from.
        """
        self.catalog_file_input.setText(str(settings.catalog_file) if settings.catalog_file else "")
        # Preserved unchanged: workers is configured per-build, not in this tab.
        self._workers = settings.workers

        # Set resolution checkboxes
        # Disconnect to avoid triggering events during setup
        try:
            self.resolution_list.itemChanged.disconnect(self._handle_resolution_selection)
        except TypeError:
            # Not connected yet on first load
            pass

        try:
            target_resolutions = settings.target_resolutions

            if target_resolutions is None:
                # None explicitly means all resolutions
                for i in range(self.resolution_list.count()):
                    item = self.resolution_list.item(i)
                    if item:
                        item.setCheckState(Qt.CheckState.Checked)
            elif len(target_resolutions) == 0:
                # Empty list means no resolutions (uncheck all)
                for i in range(self.resolution_list.count()):
                    item = self.resolution_list.item(i)
                    if item:
                        item.setCheckState(Qt.CheckState.Unchecked)
            else:
                # Specific resolutions selected
                # First uncheck all
                for i in range(self.resolution_list.count()):
                    item = self.resolution_list.item(i)
                    if item:
                        item.setCheckState(Qt.CheckState.Unchecked)

                # Check only the selected resolutions
                for i in range(1, self.resolution_list.count()):  # Skip "All" at index 0
                    item = self.resolution_list.item(i)
                    if item:
                        res_value = item.data(Qt.ItemDataRole.UserRole)
                        if res_value in target_resolutions:
                            item.setCheckState(Qt.CheckState.Checked)

                # Check "All" if all individual items are now checked
                all_checked = all(
                    item.checkState() == Qt.CheckState.Checked
                    for i in range(1, self.resolution_list.count())
                    if (item := self.resolution_list.item(i)) is not None
                )
                all_item = self.resolution_list.item(0)
                if all_item:
                    all_item.setCheckState(
                        Qt.CheckState.Checked if all_checked else Qt.CheckState.Unchecked
                    )

        finally:
            # Reconnect
            self.resolution_list.itemChanged.connect(self._handle_resolution_selection)

        # Update download button visibility
        self._update_download_buttons()

    def get_values(self) -> DatabaseBuilderSettings:
        """Get current values from widgets.

        Returns:
            DatabaseBuilderSettings: DatabaseBuilderSettings instance with current values
                from widgets
        """
        # Get values, convert empty strings to None
        catalog_text = self.catalog_file_input.text().strip()

        # Get selected resolutions
        all_item = self.resolution_list.item(0)
        all_selected = all_item and all_item.checkState() == Qt.CheckState.Checked

        # Collect individual selections
        selected_resolutions = []
        for i in range(1, self.resolution_list.count()):
            item = self.resolution_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                res_value = item.data(Qt.ItemDataRole.UserRole)
                if res_value and res_value != "all":
                    selected_resolutions.append(res_value)

        # Determine what to save:
        # - If "All" is checked OR all individual items are checked → None (means all)
        # - If specific items are checked → list of those items
        # - If nothing is checked → empty list (though this shouldn't normally happen)
        if all_selected:
            target_resolutions = None  # Explicitly None means all
        elif selected_resolutions:
            target_resolutions = selected_resolutions
        else:
            # Nothing selected - save as empty list
            target_resolutions = []

        return DatabaseBuilderSettings(
            catalog_file=Path(catalog_text) if catalog_text else None,
            target_resolutions=target_resolutions,
            # Carried through from the loaded settings (not edited in this tab).
            workers=self._workers,
        )
