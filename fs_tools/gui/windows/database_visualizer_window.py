"""Database visualizer window for browsing template database."""

import asyncio
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
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
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from fs_tools.constants import ICON_BOX_SCALE
from fs_tools.models.icon_template import IconTemplate
from fs_tools.template_db.icon_manager import IconManager
from fs_tools.template_db.template_database import TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager

logger = logging.getLogger(__name__)


class DatabaseLoader(QThread):
    """Thread for loading all databases in background."""

    finished = Signal(object)  # all_databases_dict
    error = Signal(str)

    def __init__(self, database_path: str) -> None:
        """Initialize the database loader.

        Args:
            database_path (str): Path to the database file to load.
        """
        super().__init__()
        self.database_path = database_path

    def run(self) -> None:
        """Load all databases in background thread.

        Emits:
            finished: Signal with loaded databases on success.
            error: Signal with error message on failure.
        """
        try:
            # Create TemplateManager and load all resolutions
            db_path = Path(self.database_path)
            manager = TemplateManager(database_path=db_path)

            # Load all resolutions using TemplateManager (runs async in sync context)
            all_databases = asyncio.run(manager.load_all_resolutions())

            self.finished.emit(all_databases)

        except Exception as e:
            logger.exception("Failed to load databases")
            self.error.emit(str(e))


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
        self.all_databases: dict[SupportedResolution, TemplateDatabase] = {}
        self.current_resolution: SupportedResolution | None = None
        self.database: TemplateDatabase | None = None
        self.filtered_templates: list[tuple[int, IconTemplate]] = []
        self.all_templates: list[tuple[int, IconTemplate]] = []
        self.loader_thread: DatabaseLoader | None = None
        self.selected_template: tuple[int, IconTemplate] | None = None
        self._pending_filter_state: dict[str, object] | None = None

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
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

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
        self.info_label_left.setText(t("database_visualizer.select_template"))
        self.info_label_right.setText("")
        self.save_button.setText(t("database_visualizer.save_icon"))
        self.replace_button.setText(t("database_visualizer.replace_icon"))
        self.delete_button.setText(t("database_visualizer.delete_icon"))
        self.image_group.setTitle(t("database_visualizer.template_comparison"))
        self.current_group.setTitle(t("database_visualizer.current_resolution"))
        self.highest_group.setTitle(t("database_visualizer.highest_resolution"))
        self.current_image.setText(t("database_visualizer.no_image_selected"))
        self.highest_image.setText(t("database_visualizer.no_image_selected"))

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

        # Template info and action buttons in horizontal layout
        info_layout = QHBoxLayout()

        # Two-column info layout
        info_columns_layout = QHBoxLayout()

        # Left column: code, faction, category, mod, crated
        self.info_label_left = QLabel()
        self.info_label_left.setFont(QFont("Arial", 10))
        self.info_label_left.setWordWrap(True)
        self.info_label_left.setStyleSheet(
            "QLabel { background-color: palette(alternate-base); padding: 10px; "
            "border: 1px solid palette(mid); }"
        )
        info_columns_layout.addWidget(self.info_label_left)

        # Right column: resolution, shape, index, highest res
        self.info_label_right = QLabel()
        self.info_label_right.setFont(QFont("Arial", 10))
        self.info_label_right.setWordWrap(True)
        self.info_label_right.setStyleSheet(
            "QLabel { background-color: palette(alternate-base); padding: 10px; "
            "border: 1px solid palette(mid); }"
        )
        info_columns_layout.addWidget(self.info_label_right)

        info_layout.addLayout(info_columns_layout, stretch=1)

        # Action buttons layout
        buttons_layout = QVBoxLayout()

        # Save icon button
        self.save_button = QPushButton()
        self.save_button.setEnabled(False)
        self.save_button.setMinimumWidth(120)
        self.save_button.clicked.connect(self._on_save_icon)
        buttons_layout.addWidget(self.save_button)

        # Replace icon button
        self.replace_button = QPushButton()
        self.replace_button.setEnabled(False)
        self.replace_button.setMinimumWidth(120)
        self.replace_button.clicked.connect(self._on_replace_icon)
        buttons_layout.addWidget(self.replace_button)

        # Delete icon button
        self.delete_button = QPushButton()
        self.delete_button.setEnabled(False)
        self.delete_button.setMinimumWidth(120)
        self.delete_button.clicked.connect(self._on_delete_icon)
        buttons_layout.addWidget(self.delete_button)

        info_layout.addLayout(buttons_layout)

        layout.addLayout(info_layout)

        # Image comparison area
        self.image_group = QGroupBox()
        image_layout = QHBoxLayout(self.image_group)

        # Current resolution image
        self.current_group = QGroupBox()
        current_layout = QVBoxLayout(self.current_group)
        current_scroll = QScrollArea()
        self.current_image = QLabel()
        self.current_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_image.setMinimumHeight(200)
        self.current_image.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); background-color: palette(base); }"
        )
        current_scroll.setWidget(self.current_image)
        current_scroll.setWidgetResizable(True)
        current_layout.addWidget(current_scroll)
        image_layout.addWidget(self.current_group)

        # Highest resolution image
        self.highest_group = QGroupBox()
        highest_layout = QVBoxLayout(self.highest_group)
        highest_scroll = QScrollArea()
        self.highest_image = QLabel()
        self.highest_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.highest_image.setMinimumHeight(200)
        self.highest_image.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); background-color: palette(base); }"
        )
        highest_scroll.setWidget(self.highest_image)
        highest_scroll.setWidgetResizable(True)
        highest_layout.addWidget(highest_scroll)
        image_layout.addWidget(self.highest_group)

        layout.addWidget(self.image_group)

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
            self.database = None
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
        self.save_button.setEnabled(False)
        self.replace_button.setEnabled(False)
        self.delete_button.setEnabled(False)

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
            self.database = self.all_databases[resolution]
            self.all_templates = list(enumerate(self.database.templates))

            # Update window title
            self.setWindowTitle(
                t("database_visualizer.title_with_resolution").replace(
                    "{resolution}", resolution.value
                )
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
        self.loader_thread = DatabaseLoader(self.database_path)
        self.loader_thread.finished.connect(self._on_databases_loaded)
        self.loader_thread.error.connect(self._on_database_error)
        self.loader_thread.start()

    def _on_databases_loaded(
        self, all_databases: dict[SupportedResolution, TemplateDatabase]
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

        # Check if we have a pending filter state to restore
        pending_state = getattr(self, "_pending_filter_state", None)

        if pending_state:
            # Restore filter state
            self._restore_filter_state(pending_state)
            self._pending_filter_state = None
        elif available_resolutions:
            # Select first resolution by default
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
        self.results_label.setText(
            t("database_visualizer.error_loading").replace("{error}", error_msg)
        )
        logger.error("Failed to load database: %s", error_msg)

    def _apply_filters(self) -> None:
        """Apply current filters and update the template list."""
        if not self.database:
            return

        # Get filter values (PySide6 returns enum values as strings, convert back)
        code_text = self.code_filter.text().lower()
        faction_data = self.faction_filter.currentData()
        faction = (
            ItemFaction(faction_data)
            if faction_data and not isinstance(faction_data, ItemFaction)
            else faction_data
        )
        category_data = self.category_filter.currentData()
        category = (
            ItemCategory(category_data)
            if category_data and not isinstance(category_data, ItemCategory)
            else category_data
        )
        mod = self.mod_filter.currentData()

        # Crated filter logic
        show_all_crated = self.crated_all.isChecked()
        show_normal = self.crated_normal.isChecked()
        show_crated = self.crated_crated.isChecked()

        # Filter templates
        filtered: list[tuple[int, IconTemplate]] = []
        for idx, template in self.all_templates:
            # Code filter
            if code_text and code_text not in template.code.lower():
                continue

            # Faction filter
            if faction and template.faction != faction:
                continue

            # Category filter
            if category and template.category != category:
                continue

            # Mod filter
            if mod and template.mod != mod:
                continue

            # Crated filter
            if not show_all_crated:
                if template.crated and not show_crated:
                    continue
                if not template.crated and not show_normal:
                    continue

            filtered.append((idx, template))

        self.filtered_templates = filtered
        self._update_template_list()

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
            t("database_visualizer.showing_results")
            .replace("{filtered}", str(filtered))
            .replace("{total}", str(total))
        )

    def _on_template_selected(self, item: QListWidgetItem) -> None:
        """Handle template selection.

        Args:
            item (QListWidgetItem): The selected list item.
        """
        idx, template = item.data(Qt.ItemDataRole.UserRole)

        # Store selected template and enable action buttons
        self.selected_template = (idx, template)
        self.save_button.setEnabled(True)
        self.replace_button.setEnabled(True)
        self.delete_button.setEnabled(True)

        # Find highest resolution available
        highest_resolution = max(self.all_databases.keys(), key=lambda x: int(x.value))

        # Find the same template in highest resolution
        highest_template = None
        if highest_resolution in self.all_databases:
            highest_db = self.all_databases[highest_resolution]
            for high_template in highest_db.templates:
                if (
                    high_template.code == template.code
                    and high_template.faction == template.faction
                    and high_template.mod == template.mod
                    and high_template.crated == template.crated
                    and high_template.category == template.category
                ):
                    highest_template = high_template
                    break

        # Update info labels (two columns)
        # Left column: code, faction, category, mod, crated
        info_text_left = (
            f"<b>{t('database_visualizer.info.code')}</b> {template.code}<br>"
            f"<b>{t('database_visualizer.info.faction')}</b> {template.faction.value}<br>"
            f"<b>{t('database_visualizer.info.category')}</b> {template.category.value}<br>"
            f"<b>{t('database_visualizer.info.mod')}</b> {template.mod}<br>"
            f"<b>{t('database_visualizer.info.crated')}</b> {template.crated}"
        )
        self.info_label_left.setText(info_text_left)

        # Right column: resolution, shape, index, highest res
        current_res = f"{template.resolution.value}px"
        if highest_template:
            highest_info = (
                f"<b>{t('database_visualizer.info.highest_res_available')}</b> "
                f"{highest_template.resolution.value}px ({highest_template.image.shape})"
            )
        else:
            not_found_msg = t("database_visualizer.info.highest_res_not_found")
            not_found_msg = not_found_msg.replace("{resolution}", highest_resolution.value)
            highest_info = f"<b>{not_found_msg}</b>"

        info_text_right = (
            f"<b>{t('database_visualizer.info.current_resolution')}</b> {current_res}<br>"
            f"<b>{t('database_visualizer.info.current_shape')}</b> {template.image.shape}<br>"
            f"<b>{t('database_visualizer.info.database_index')}</b> {idx}<br>"
            f"{highest_info}"
        )
        self.info_label_right.setText(info_text_right)

        # Display comparison images
        self._display_comparison_images(template, highest_template)

    def _display_comparison_images(
        self, current_template: IconTemplate | None, highest_template: IconTemplate | None
    ) -> None:
        """Display current and highest resolution templates at matching sizes.

        Args:
            current_template (IconTemplate | None): The currently selected template.
            highest_template (IconTemplate | None): The highest resolution template.
        """
        if not current_template:
            return

        # Get dimensions
        current_rgb = cv2.cvtColor(current_template.image, cv2.COLOR_BGR2RGB)
        current_h, current_w, current_ch = current_rgb.shape

        # Display current resolution image (scaled to match target size)
        current_bytes_per_line = current_ch * current_w
        current_qt_image = QImage(
            current_rgb.data.tobytes(),
            current_w,
            current_h,
            current_bytes_per_line,
            QImage.Format.Format_RGB888,
        )
        current_pixmap = QPixmap.fromImage(current_qt_image)

        # Calculate target size and scale based on highest resolution
        if highest_template:
            highest_rgb = cv2.cvtColor(highest_template.image, cv2.COLOR_BGR2RGB)
            highest_h, highest_w, highest_ch = highest_rgb.shape

            # Target size: highest resolution at 4x scale
            target_width = highest_w * 4
            target_height = highest_h * 4

            # Calculate scale factor for current resolution to match target size
            current_scale_x = target_width / current_w
            current_scale_y = target_height / current_h
            current_scale = min(current_scale_x, current_scale_y)  # Keep aspect ratio

            # Scale and display current image
            current_scaled = current_pixmap.scaled(
                int(current_w * current_scale),
                int(current_h * current_scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )

            # Display highest resolution image (4x)
            highest_bytes_per_line = highest_ch * highest_w
            highest_qt_image = QImage(
                highest_rgb.data.tobytes(),
                highest_w,
                highest_h,
                highest_bytes_per_line,
                QImage.Format.Format_RGB888,
            )
            highest_pixmap = QPixmap.fromImage(highest_qt_image)

            # Scale highest to 4x
            highest_scaled = highest_pixmap.scaled(
                target_width,
                target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )

            self.highest_image.setPixmap(highest_scaled)
            self.highest_image.resize(highest_scaled.size())

            # Update group box title with highest resolution
            self.highest_group.setTitle(
                t("database_visualizer.highest_resolution_found").replace(
                    "{resolution}", highest_template.resolution.value
                )
            )
        else:
            # Fallback: use 8x for current if no highest template
            current_scale = 8.0

            current_scaled = current_pixmap.scaled(
                int(current_w * current_scale),
                int(current_h * current_scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )

            # No highest resolution template found
            self.highest_image.setText(t("database_visualizer.template_not_found"))
            self.highest_group.setTitle(t("database_visualizer.highest_resolution_not_found"))

        self.current_image.setPixmap(current_scaled)
        self.current_image.resize(current_scaled.size())

        # Update group box title with current resolution and scale
        self.current_group.setTitle(
            t("database_visualizer.current_resolution_scale")
            .replace("{resolution}", current_template.resolution.value)
            .replace("{scale}", f"{current_scale:.1f}")
        )

    def _on_replace_icon(self) -> None:
        """Handle replace icon button click."""
        if not self.selected_template or not self.current_resolution or not self.database_path:
            return

        _idx, template = self.selected_template

        # Open file dialog to select new icon
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("database_visualizer.select_replacement_icon"),
            "",
            "PNG Files (*.png);;All Files (*)",
        )

        if not file_path:
            return

        # Calculate expected icon size for this resolution
        expected_size = int(ICON_BOX_SCALE * int(self.current_resolution.value))

        # Load the image
        try:
            loaded_image = Image.open(file_path)
        except Exception as e:
            self._show_replace_error(str(e))
            return

        # Convert to RGB if necessary (handle RGBA, palette, etc.)
        if loaded_image.mode == "RGBA":
            background = Image.new("RGB", loaded_image.size, (0, 0, 0))
            background.paste(loaded_image, mask=loaded_image.split()[3])
            pil_image: Image.Image = background
        elif loaded_image.mode != "RGB":
            pil_image = loaded_image.convert("RGB")
        else:
            pil_image = loaded_image

        # Resize to expected size using high-quality resampling
        if pil_image.size != (expected_size, expected_size):
            pil_image = pil_image.resize(
                (expected_size, expected_size),
                Image.Resampling.LANCZOS,
            )

        # Convert to OpenCV format (BGR)
        rgb_array = np.array(pil_image)
        bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

        # Replace the icon in the database
        try:
            manager = IconManager(
                database_path=Path(self.database_path),
                databases=self.all_databases,
                icon_scale=ICON_BOX_SCALE,
            )
            manager.add_icon_from_image(
                icon_image=bgr_array,
                item_code=template.code,
                faction=template.faction,
                category=template.category,
                crated=template.crated,
                mod=template.mod,
                resolution=self.current_resolution,
                replace=True,
            )
            TemplateManager.save_single_resolution(
                database=self.all_databases[self.current_resolution],
                resolution=self.current_resolution,
                output_path=Path(self.database_path),
            )
        except Exception as e:
            self._show_replace_error(str(e))
            return

        # Show success message
        QMessageBox.information(
            self,
            t("database_visualizer.replace_success_title"),
            t("database_visualizer.replace_success_message").replace("{code}", template.code),
        )

        # Update the UI without full reload
        self._apply_filters()

    def _on_save_icon(self) -> None:
        """Handle save icon button click."""
        if not self.selected_template:
            return

        _idx, template = self.selected_template

        # Open file dialog to select save location
        crated_suffix = "_crated" if template.crated else ""
        default_name = f"{template.code}{crated_suffix}_{template.resolution.value}p.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            t("database_visualizer.save_icon_dialog"),
            default_name,
            "PNG Files (*.png);;All Files (*)",
        )

        if not file_path:
            return

        # Save the icon image
        try:
            cv2.imwrite(file_path, template.image)
        except Exception as e:
            logger.exception("Failed to save icon")
            QMessageBox.critical(
                self,
                t("database_visualizer.save_error_title"),
                t("database_visualizer.save_error_message").replace("{error}", str(e)),
            )
            return

        QMessageBox.information(
            self,
            t("database_visualizer.save_success_title"),
            t("database_visualizer.save_success_message").replace("{path}", file_path),
        )

    def _on_delete_icon(self) -> None:
        """Handle delete icon button click."""
        if not self.selected_template or not self.current_resolution or not self.database_path:
            return

        _idx, template = self.selected_template

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            t("database_visualizer.delete_confirm_title"),
            t("database_visualizer.delete_confirm_message")
            .replace("{code}", template.code)
            .replace("{resolution}", self.current_resolution.value),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete the icon from the database
        try:
            manager = IconManager(
                database_path=Path(self.database_path),
                databases=self.all_databases,
                icon_scale=ICON_BOX_SCALE,
            )
            manager.delete_icon(
                item_code=template.code,
                faction=template.faction,
                category=template.category,
                crated=template.crated,
                mod=template.mod,
                resolution=self.current_resolution,
            )
            TemplateManager.save_single_resolution(
                database=self.all_databases[self.current_resolution],
                resolution=self.current_resolution,
                output_path=Path(self.database_path),
            )
        except Exception as e:
            logger.exception("Failed to delete icon")
            QMessageBox.critical(
                self,
                t("database_visualizer.delete_error_title"),
                t("database_visualizer.delete_error_message").replace("{error}", str(e)),
            )
            return

        QMessageBox.information(
            self,
            t("database_visualizer.delete_success_title"),
            t("database_visualizer.delete_success_message").replace("{code}", template.code),
        )

        # Clear selection and disable buttons
        self.selected_template = None
        self.save_button.setEnabled(False)
        self.replace_button.setEnabled(False)
        self.delete_button.setEnabled(False)

        # Clear details panel
        self.info_label_left.setText(t("database_visualizer.select_template"))
        self.info_label_right.setText("")
        self.current_image.clear()
        self.current_image.setText(t("database_visualizer.no_image_selected"))
        self.highest_image.clear()
        self.highest_image.setText(t("database_visualizer.no_image_selected"))

        # Refresh template list from the modified database
        if self.database:
            self.all_templates = list(enumerate(self.database.templates))
            self._apply_filters()

    def _get_current_filter_state(self) -> dict[str, object]:
        """Get the current state of all filters.

        Returns:
            dict[str, object]: Dictionary containing current filter values.
        """
        return {
            "resolution": self.resolution_filter.currentData(),
            "code": self.code_filter.text(),
            "faction": self.faction_filter.currentData(),
            "category": self.category_filter.currentData(),
            "mod": self.mod_filter.currentData(),
            "crated_all": self.crated_all.isChecked(),
            "crated_normal": self.crated_normal.isChecked(),
            "crated_crated": self.crated_crated.isChecked(),
        }

    def _restore_filter_state(self, state: dict[str, object]) -> None:
        """Restore filter state after database reload.

        Args:
            state (dict[str, object]): Dictionary containing filter values to restore.
        """
        # Restore resolution
        if state["resolution"]:
            index = self.resolution_filter.findData(state["resolution"])
            if index >= 0:
                self.resolution_filter.setCurrentIndex(index)

        # Restore code filter
        self.code_filter.setText(str(state["code"]) if state["code"] else "")

        # Restore faction filter
        if state["faction"]:
            index = self.faction_filter.findData(state["faction"])
            if index >= 0:
                self.faction_filter.setCurrentIndex(index)

        # Restore category filter
        if state["category"]:
            index = self.category_filter.findData(state["category"])
            if index >= 0:
                self.category_filter.setCurrentIndex(index)

        # Restore mod filter (handled in _on_resolution_changed, but set if available)
        if state["mod"]:
            index = self.mod_filter.findData(state["mod"])
            if index >= 0:
                self.mod_filter.setCurrentIndex(index)

        # Restore crated checkboxes
        self.crated_all.setChecked(bool(state["crated_all"]))
        self.crated_normal.setChecked(bool(state["crated_normal"]))
        self.crated_crated.setChecked(bool(state["crated_crated"]))

    def _reload_preserving_filters(self) -> None:
        """Reload databases while preserving current filter state."""
        # Save current filter state
        filter_state = self._get_current_filter_state()

        # Clear selection and disable buttons
        self.selected_template = None
        self.save_button.setEnabled(False)
        self.replace_button.setEnabled(False)
        self.delete_button.setEnabled(False)

        # Store filter state to restore after load completes
        self._pending_filter_state = filter_state

        # Reload databases
        self.load_databases()

    def _show_replace_error(self, error: str) -> None:
        """Show error message for failed icon replacement.

        Args:
            error (str): Error message to display.
        """
        logger.exception("Failed to replace icon")
        QMessageBox.critical(
            self,
            t("database_visualizer.replace_error_title"),
            t("database_visualizer.replace_error_message").replace("{error}", error),
        )

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
