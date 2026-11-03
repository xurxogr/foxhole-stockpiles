"""Database visualizer window for browsing template database."""

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import on_language_changed, t
from fs_tools.core.template_store import read_resolution
from fs_tools.gui.utils.database_loader_worker import DatabaseLoaderWorker
from fs_tools.gui.utils.template_icon_actions import TemplateIconActions
from fs_tools.gui.widgets.icon_detail_panel import IconDetailPanel
from fs_tools.models.icon_template import IconTemplate

logger = logging.getLogger(__name__)


class DatabaseVisualizerWindow(QDialog):
    """Window for browsing and visualizing template database."""

    def __init__(self, parent: QWidget | None = None, database_path: str | None = None) -> None:
        """Initialize the database visualizer window.

        Args:
            parent (QWidget | None): Parent widget.
            database_path (str | None): Path to the database file to load.
        """
        super().__init__(parent)
        self.database_path = database_path
        self.all_databases: dict[SupportedResolution, list[IconTemplate]] = {}
        self.current_resolution: SupportedResolution | None = None
        self.current_templates: list[IconTemplate] | None = None
        self.filtered_templates: list[tuple[int, IconTemplate]] = []
        self.all_templates: list[tuple[int, IconTemplate]] = []
        self.loader_thread: DatabaseLoaderWorker | None = None
        self.selected_template: tuple[int, IconTemplate] | None = None
        self.icon_actions = TemplateIconActions(view=self, parent=self)

        self.init_ui()

        if database_path:
            self.load_databases()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)

        # Main layout
        main_layout = QHBoxLayout(self)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - filters and list
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel - image display
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Set initial splitter proportions (30% left, 70% right)
        splitter.setSizes([400, 1000])

        # Apply translations
        self.retranslate()

        # Connect to language change signal with cleanup
        on_language_changed(self._on_language_changed)

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("database_visualizer.title"))
        self.database_group.setTitle(t("database_visualizer.database_group"))
        self.browse_button.setText(t("common.browse"))
        self.filters_group.setTitle(t("database_visualizer.filters_group"))
        self.resolution_label.setText(t("database_visualizer.resolution"))
        self.code_label.setText(t("database_visualizer.code"))
        self.code_filter.setPlaceholderText(t("database_visualizer.code_placeholder"))
        self.faction_label.setText(t("database_visualizer.faction"))
        self.category_label.setText(t("database_visualizer.category"))
        self.mod_label.setText(t("database_visualizer.mod"))
        self.crated_label.setText(t("database_visualizer.crated"))
        self.crated_all.setText(t("database_visualizer.crated_all"))
        self.crated_normal.setText(t("database_visualizer.crated_normal"))
        self.crated_crated.setText(t("database_visualizer.crated_crated"))
        self.clear_button.setText(t("database_visualizer.clear_filters"))
        self.detail_panel.retranslate()

    def _create_left_panel(self) -> QWidget:
        """Create the left panel with filters and template list.

        Returns:
            QWidget: The left panel widget.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Filters section
        self.filters_group = QGroupBox()
        filters_layout = QGridLayout(self.filters_group)

        # Resolution filter
        self.resolution_label = QLabel()
        filters_layout.addWidget(self.resolution_label, 0, 0)
        self.resolution_filter = QComboBox()
        self.resolution_filter.addItem("Loading...", None)
        self.resolution_filter.currentTextChanged.connect(self._on_resolution_changed)
        filters_layout.addWidget(self.resolution_filter, 0, 1)

        # Code filter
        self.code_label = QLabel()
        filters_layout.addWidget(self.code_label, 1, 0)
        self.code_filter = QLineEdit()
        self.code_filter.textChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.code_filter, 1, 1)

        # Faction filter
        self.faction_label = QLabel()
        filters_layout.addWidget(self.faction_label, 2, 0)
        self.faction_filter = QComboBox()
        self.faction_filter.addItem(t("common.all"), None)
        for faction in ItemFaction:
            self.faction_filter.addItem(faction.value, faction)
        self.faction_filter.currentTextChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.faction_filter, 2, 1)

        # Category filter
        self.category_label = QLabel()
        filters_layout.addWidget(self.category_label, 3, 0)
        self.category_filter = QComboBox()
        self.category_filter.addItem(t("common.all"), None)
        for category in ItemCategory:
            self.category_filter.addItem(category.value, category)
        self.category_filter.currentTextChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.category_filter, 3, 1)

        # Mod filter
        self.mod_label = QLabel()
        filters_layout.addWidget(self.mod_label, 4, 0)
        self.mod_filter = QComboBox()
        self.mod_filter.addItem(t("common.all"), "")
        self.mod_filter.currentTextChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.mod_filter, 4, 1)

        # Crated filter
        self.crated_label = QLabel()
        filters_layout.addWidget(self.crated_label, 5, 0)
        crated_layout = QHBoxLayout()
        self.crated_all = QCheckBox()
        self.crated_normal = QCheckBox()
        self.crated_crated = QCheckBox()
        self.crated_all.setChecked(True)
        self.crated_all.toggled.connect(self._on_crated_all_toggled)
        self.crated_normal.toggled.connect(self._apply_filters)
        self.crated_crated.toggled.connect(self._apply_filters)
        crated_layout.addWidget(self.crated_all)
        crated_layout.addWidget(self.crated_normal)
        crated_layout.addWidget(self.crated_crated)
        filters_layout.addLayout(crated_layout, 5, 1)

        # Clear filters button
        self.clear_button = QPushButton()
        self.clear_button.clicked.connect(self._clear_filters)
        filters_layout.addWidget(self.clear_button, 6, 0, 1, 2)

        layout.addWidget(self.filters_group)

        # Loading progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Results count
        self.results_label = QLabel()
        layout.addWidget(self.results_label)

        # Template list
        self.template_list = QListWidget()
        self.template_list.itemClicked.connect(self._on_template_selected)
        layout.addWidget(self.template_list)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create the right panel for image display.

        Returns:
            QWidget: The right panel widget.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Database selection section at the top
        self.database_group = QGroupBox()
        database_layout = QHBoxLayout(self.database_group)
        self.database_path_edit = QLineEdit()
        self.database_path_edit.setReadOnly(True)
        self.database_path_edit.setText(self.database_path or "")
        database_layout.addWidget(self.database_path_edit)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._on_browse_database)
        database_layout.addWidget(self.browse_button)
        layout.addWidget(self.database_group)

        self.detail_panel = IconDetailPanel()
        self.detail_panel.save_button.clicked.connect(self.icon_actions.on_save_icon)
        self.detail_panel.replace_button.clicked.connect(self.icon_actions.on_replace_icon)
        self.detail_panel.delete_button.clicked.connect(self.icon_actions.on_delete_icon)
        layout.addWidget(self.detail_panel)

        return panel

    def _on_browse_database(self) -> None:
        """Handle browse database button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("database_visualizer.select_database"),
            self.database_path or "",
            t("database_visualizer.database_filter"),
        )
        if file_path:
            self.database_path = file_path
            self.database_path_edit.setText(file_path)
            # Clear current state
            self.all_databases.clear()
            self.all_templates.clear()
            self.filtered_templates.clear()
            self.template_list.clear()
            self.selected_template = None
            self.current_templates = None
            self.current_resolution = None
            # Reset resolution filter
            self.resolution_filter.blockSignals(True)
            self.resolution_filter.clear()
            self.resolution_filter.addItem("Loading...", None)
            self.resolution_filter.blockSignals(False)
            # Load new database
            self.load_databases()

    def _on_crated_all_toggled(self, checked: bool) -> None:
        """Handle 'All' crated checkbox toggle.

        Args:
            checked (bool): Whether the checkbox is checked.
        """
        if checked:
            self.crated_normal.setChecked(False)
            self.crated_crated.setChecked(False)
        self._apply_filters()

    def _clear_filters(self) -> None:
        """Clear all filters."""
        self.code_filter.clear()
        self.faction_filter.setCurrentIndex(0)
        self.category_filter.setCurrentIndex(0)
        self.mod_filter.setCurrentIndex(0)
        self.crated_all.setChecked(True)
        self.crated_normal.setChecked(False)
        self.crated_crated.setChecked(False)

    def _on_resolution_changed(self) -> None:
        """Handle resolution change."""
        # Clear selected template when resolution changes
        self.selected_template = None
        self.detail_panel.set_actions_enabled(False)

        # PySide6 returns enum value as string, convert back to enum
        resolution_data = self.resolution_filter.currentData()
        if not resolution_data:
            return
        resolution = (
            resolution_data
            if isinstance(resolution_data, SupportedResolution)
            else SupportedResolution(resolution_data)
        )
        if resolution in self.all_databases:
            self.current_resolution = resolution
            self.current_templates = self.all_databases[resolution]
            self.all_templates = list(enumerate(self.current_templates))

            # Update window title
            self.setWindowTitle(
                t("database_visualizer.title_with_resolution", resolution=resolution.value)
            )

            # Populate mod filter with available mods for this resolution
            mods = sorted(set(tmpl.mod for _, tmpl in self.all_templates))
            current_mod = self.mod_filter.currentData()
            self.mod_filter.clear()
            self.mod_filter.addItem(t("common.all"), "")
            for mod in mods:
                self.mod_filter.addItem(mod, mod)

            # Restore mod selection if it exists in new resolution
            if current_mod:
                index = self.mod_filter.findData(current_mod)
                if index >= 0:
                    self.mod_filter.setCurrentIndex(index)

            # Apply filters with new data
            self._apply_filters()

    def load_databases(self) -> None:
        """Load all template databases in background thread."""
        if not self.database_path:
            self.results_label.setText(t("database_visualizer.no_database_path"))
            return

        self.results_label.setText(t("database_visualizer.loading_databases"))
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        # Create and start loader thread
        self.loader_thread = DatabaseLoaderWorker(self.database_path)
        self.loader_thread.databases_loaded.connect(self._on_databases_loaded)
        self.loader_thread.error.connect(self._on_database_error)
        self.loader_thread.start()

    def _on_databases_loaded(
        self, all_databases: dict[SupportedResolution, list[IconTemplate]]
    ) -> None:
        """Handle successful database loading.

        Args:
            all_databases (dict): Dictionary of resolution to database mappings.
        """
        self.all_databases = all_databases

        # Populate resolution filter
        self.resolution_filter.clear()
        available_resolutions = sorted(all_databases.keys(), key=lambda x: int(x.value))

        for resolution in available_resolutions:
            self.resolution_filter.addItem(f"{resolution.value}p", resolution)

        # Select first resolution by default
        if available_resolutions:
            self.resolution_filter.setCurrentIndex(0)
            # This will trigger _on_resolution_changed

        # Hide progress
        self.progress_bar.setVisible(False)

    def _on_database_error(self, error_msg: str) -> None:
        """Handle database loading error.

        Args:
            error_msg (str): Error message.
        """
        self.progress_bar.setVisible(False)
        self.results_label.setText(t("database_visualizer.error_loading", error=error_msg))
        logger.error("Failed to load database: %s", error_msg)

    def _apply_filters(self) -> None:
        """Apply current filters and update the template list."""
        if self.current_templates is None:
            return

        matches = self._build_template_filter()
        self.filtered_templates = [
            (idx, template) for idx, template in self.all_templates if matches(template)
        ]
        self._update_template_list()

    def _build_template_filter(self) -> Callable[[IconTemplate], bool]:
        """Read the filter widgets into one check of a template.

        Returns:
            Callable[[IconTemplate], bool]: Whether a template passes every filter.
        """
        # PySide6 returns enum values as strings, convert back
        code_text = self.code_filter.text().lower()
        faction_data = self.faction_filter.currentData()
        faction = ItemFaction(faction_data) if faction_data else None
        category_data = self.category_filter.currentData()
        category = ItemCategory(category_data) if category_data else None
        mod = self.mod_filter.currentData()
        show_all_crated = self.crated_all.isChecked()
        show_normal = self.crated_normal.isChecked()
        show_crated = self.crated_crated.isChecked()

        def matches(template: IconTemplate) -> bool:
            """Check a template against the filters read.

            Args:
                template (IconTemplate): The template.

            Returns:
                bool: Whether it passes every filter.
            """
            return (
                code_text in template.code.lower()
                and (not faction or template.faction == faction)
                and (not category or template.category == category)
                and (not mod or template.mod == mod)
                and (show_all_crated or (show_crated if template.crated else show_normal))
            )

        return matches

    def _update_template_list(self) -> None:
        """Update the template list widget."""
        self.template_list.clear()

        for idx, template in self.filtered_templates:
            crated_str = " (crated)" if template.crated else ""
            item_text = f"{template.code}{crated_str} | {template.faction.value} | {template.mod}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, (idx, template))
            self.template_list.addItem(item)

        # Update results count
        total = len(self.all_templates)
        filtered = len(self.filtered_templates)
        self.results_label.setText(
            t("database_visualizer.showing_results", filtered=str(filtered), total=str(total))
        )

    def _on_template_selected(self, item: QListWidgetItem) -> None:
        """Handle template selection.

        Args:
            item (QListWidgetItem): The selected list item.
        """
        idx, template = item.data(Qt.ItemDataRole.UserRole)

        # Store selected template and enable action buttons
        self.selected_template = (idx, template)
        self.detail_panel.set_actions_enabled(True)

        # Find highest resolution available
        highest_resolution = max(self.all_databases.keys(), key=lambda x: int(x.value))

        # Find the same template in highest resolution
        highest_template = None
        if highest_resolution in self.all_databases:
            for high_template in self.all_databases[highest_resolution]:
                if (
                    high_template.code == template.code
                    and high_template.faction == template.faction
                    and high_template.mod == template.mod
                    and high_template.crated == template.crated
                    and high_template.category == template.category
                ):
                    highest_template = high_template
                    break

        self.detail_panel.show_template(
            index=idx,
            template=template,
            highest_template=highest_template,
            highest_resolution=highest_resolution,
        )

    def clear_selection(self) -> None:
        """Forget the selected template and clear its details."""
        self.selected_template = None
        self.detail_panel.set_actions_enabled(False)
        self.detail_panel.clear_details()

    def reload_current_resolution(self) -> None:
        """Re-read the current resolution's templates after an edit and refresh the list."""
        if not self.current_resolution or not self.database_path:
            return
        templates = read_resolution(Path(self.database_path), self.current_resolution)
        self.all_databases[self.current_resolution] = templates
        self.current_templates = templates
        self.all_templates = list(enumerate(templates))
        self._apply_filters()

    def closeEvent(self, event: object) -> None:
        """Handle window close event.

        Args:
            event (object): Close event.
        """
        # Wait for loader thread to finish if running
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.wait()

        if hasattr(event, "accept"):
            event.accept()
