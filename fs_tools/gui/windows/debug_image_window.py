"""Debug image viewer window for analyzing screenshot scanning results."""

import asyncio
import logging
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.image_io import resize_bgr, swap_rb
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from fs_tools.gui.utils.image_scan_worker import ImageScanWorker
from fs_tools.models.detected_icon_info import DetectedIconInfo
from fs_tools.models.scan_result import ScanResult
from fs_tools.template_db.template_database import TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager

logger = logging.getLogger(__name__)


def _draw_box(
    image: np.ndarray,
    x: int,
    y: int,
    size: int,
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 3,
) -> None:
    """Draw a hollow rectangle outline on a BGR image, in place.

    Args:
        image (np.ndarray): BGR image to draw on (modified in place).
        x (int): Left coordinate of the box.
        y (int): Top coordinate of the box.
        size (int): Box width/height in pixels.
        color (tuple[int, int, int]): BGR color. Defaults to green.
        thickness (int): Border thickness in pixels. Defaults to 3.
    """
    h, w = image.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + size, w), min(y + size, h)
    if x1 <= x0 or y1 <= y0:
        return
    image[y0 : min(y0 + thickness, y1), x0:x1] = color
    image[max(y1 - thickness, y0) : y1, x0:x1] = color
    image[y0:y1, x0 : min(x0 + thickness, x1)] = color
    image[y0:y1, max(x1 - thickness, x0) : x1] = color


# Default tuning values for the debug viewer's match controls.
DEFAULT_PHASH_THRESHOLD = 15
DEFAULT_MAX_NCC_CANDIDATES = 50


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
            db_path = Path(self.database_path)
            manager = TemplateManager(database_path=db_path)
            all_databases = asyncio.run(manager.load_all_resolutions())
            self.finished.emit(all_databases)
        except Exception as e:
            logger.exception("Failed to load databases")
            self.error.emit(str(e))


class DebugImageWindow(QDialog):
    """Debug window for analyzing screenshot scanning results.

    Allows users to:
    1. Load a screenshot
    2. Run the scanning pipeline
    3. View detected items in a clickable list
    4. Click an item to highlight it in the screenshot and compare with templates
    """

    def __init__(self, parent: QWidget | None = None, database_path: str | None = None) -> None:
        """Initialize the debug image window.

        Args:
            parent (QWidget | None): Parent widget.
            database_path (str | None): Path to the database file to load.
        """
        super().__init__(parent)
        self.database_path = database_path
        self.all_databases: dict[SupportedResolution, TemplateDatabase] = {}
        self.scan_result: ScanResult | None = None
        self.selected_icon: DetectedIconInfo | None = None

        self.loader_thread: DatabaseLoader | None = None
        self.scan_worker: ImageScanWorker | None = None

        self.init_ui()

        if database_path:
            self.load_databases()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("debug_viewer.title"))
        self.browse_button.setText(t("common.browse"))
        self.items_group.setTitle(t("debug_viewer.detected_items"))
        self.screenshot_group.setTitle(t("debug_viewer.screenshot"))
        self.comparison_group.setTitle(t("debug_viewer.icon_comparison"))
        self.comparison_group.setToolTip(t("debug_viewer.icon_comparison_tooltip"))

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setMinimumSize(1400, 800)
        self.resize(1600, 900)

        main_layout = QVBoxLayout(self)

        # Top bar: Browse button and path (single line height)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._on_browse_screenshot)
        top_bar.addWidget(self.browse_button)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        top_bar.addWidget(self.path_edit, stretch=1)

        main_layout.addLayout(top_bar)

        # Top content: items list (left) + screenshot (right)
        top_content = QHBoxLayout()

        # Left panel: Detected items list (fixed width)
        left_panel = self._create_left_panel()
        top_content.addWidget(left_panel)

        # Screenshot panel (expandable)
        screenshot_panel = self._create_screenshot_panel()
        top_content.addWidget(screenshot_panel, stretch=1)

        main_layout.addLayout(top_content, stretch=1)

        # Bottom: Icon comparison (full width)
        comparison_panel = self._create_comparison_panel()
        main_layout.addWidget(comparison_panel)

        # Apply translations
        self.retranslate()

    def _create_left_panel(self) -> QWidget:
        """Create the left panel with detected items list.

        Returns:
            QWidget: The left panel widget.
        """
        panel = QWidget()
        panel.setFixedWidth(350)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.items_group = QGroupBox()
        items_layout = QVBoxLayout(self.items_group)

        self.items_list = QListWidget()
        self.items_list.currentItemChanged.connect(self._on_item_changed)
        items_layout.addWidget(self.items_list)

        layout.addWidget(self.items_group)
        return panel

    def _create_screenshot_panel(self) -> QWidget:
        """Create the screenshot display panel.

        Returns:
            QWidget: The screenshot panel widget.
        """
        self.screenshot_group = QGroupBox()
        screenshot_layout = QVBoxLayout(self.screenshot_group)

        # Summary line (stockpile type, name, shard, time) - single line only
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(False)
        self.summary_label.setFixedHeight(20)
        self.summary_label.setStyleSheet("QLabel { color: palette(text); padding: 2px; }")
        screenshot_layout.addWidget(self.summary_label)

        screenshot_scroll = QScrollArea()
        screenshot_scroll.setWidgetResizable(True)
        self.screenshot_label = QLabel()
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setStyleSheet("QLabel { background-color: palette(base); }")
        screenshot_scroll.setWidget(self.screenshot_label)
        screenshot_layout.addWidget(screenshot_scroll)

        return self.screenshot_group

    def _create_comparison_panel(self) -> QWidget:
        """Create the icon comparison panel (full width at bottom).

        Returns:
            QWidget: The comparison panel widget.
        """
        self.comparison_group = QGroupBox()
        self.comparison_group.setFixedHeight(305)
        comparison_layout = QVBoxLayout(self.comparison_group)

        comparison_scroll = QScrollArea()
        comparison_scroll.setWidgetResizable(True)
        self.comparison_widget = QWidget()
        self.comparison_layout = QHBoxLayout(self.comparison_widget)
        self.comparison_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        comparison_scroll.setWidget(self.comparison_widget)
        comparison_layout.addWidget(comparison_scroll)

        # Settings spinboxes (will be added to comparison layout dynamically)
        self.phash_spinbox: QSpinBox | None = None
        self.ncc_spinbox: QSpinBox | None = None

        return self.comparison_group

    def _on_browse_screenshot(self) -> None:
        """Handle browse screenshot button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("debug_viewer.select_screenshot"),
            "",
            t("common.image_filter"),
        )
        if file_path:
            self.path_edit.setText(file_path)
            self._scan_screenshot(file_path)

    def _scan_screenshot(self, file_path: str) -> None:
        """Start scanning the screenshot.

        Args:
            file_path (str): Path to the screenshot file.
        """
        if not self.database_path:
            QMessageBox.warning(
                self,
                t("tools_window.no_database_title"),
                t("tools_window.no_database_message"),
            )
            return

        # Clear previous results
        self.items_list.clear()
        self.screenshot_label.clear()
        self._clear_comparison()
        self.scan_result = None
        self.selected_icon = None

        # Start scan worker
        self.scan_worker = ImageScanWorker(file_path, Path(self.database_path))
        self.scan_worker.scan_finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _on_scan_finished(self, result: ScanResult) -> None:
        """Handle successful scan completion.

        Args:
            result (ScanResult): The scan result containing stockpile and icons.
        """
        self.scan_result = result

        # Update summary line
        self._update_summary(result)

        # Populate items list
        for icon_info in result.detected_icons:
            crated_str = " [Crated]" if icon_info.crated else ""
            item_text = (
                f"{icon_info.index:03d}: {icon_info.code}{crated_str} "
                f"x{icon_info.quantity} ({icon_info.confidence:.1%})"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, icon_info)
            self.items_list.addItem(item)

        # Display screenshot
        self._display_screenshot(result.original_image)

        # Auto-select first item
        if self.items_list.count() > 0:
            self.items_list.setCurrentRow(0)
            self.items_list.setFocus()

    def _update_summary(self, result: ScanResult) -> None:
        """Update the summary label with stockpile info.

        Args:
            result (ScanResult): The scan result containing stockpile data.
        """
        stockpile = result.stockpile
        parts = []

        # Stockpile type (may be enum or string depending on serialization)
        if stockpile.type:
            type_str = (
                stockpile.type.value if hasattr(stockpile.type, "value") else str(stockpile.type)
            )
        else:
            type_str = t("debug_viewer.unknown")
        parts.append(f"<b>{t('debug_viewer.summary_type')}:</b> {type_str}")

        # Stockpile name (if present)
        if stockpile.name:
            parts.append(f"<b>{t('debug_viewer.summary_name')}:</b> {stockpile.name}")

        # Shard
        if stockpile.shard:
            parts.append(f"<b>{t('debug_viewer.summary_shard')}:</b> {stockpile.shard}")

        # In-game time
        if stockpile.ingame_timestamp:
            parts.append(f"<b>{t('debug_viewer.summary_time')}:</b> {stockpile.ingame_timestamp}")

        self.summary_label.setText("  |  ".join(parts))

    def _on_scan_error(self, error_msg: str) -> None:
        """Handle scan error.

        Args:
            error_msg (str): Error message.
        """
        logger.error("Scan failed: %s", error_msg)
        QMessageBox.warning(
            self,
            t("debug_viewer.scan_error_title"),
            error_msg,
        )

    def _display_screenshot(
        self, image: np.ndarray, highlight_icon: DetectedIconInfo | None = None
    ) -> None:
        """Display the screenshot with optional icon highlight.

        Args:
            image (np.ndarray): Image to display (BGR format).
            highlight_icon (DetectedIconInfo | None): Icon to highlight with green box.
        """
        display_image = image.copy()

        # Draw green rectangle around highlighted icon
        if highlight_icon:
            x, y = highlight_icon.position
            size = highlight_icon.size
            _draw_box(display_image, x, y, size)

        # Convert BGR to RGB for Qt
        rgb_image = swap_rb(display_image)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        qt_image = QImage(
            rgb_image.data.tobytes(),
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )

        # Scale to fit while maintaining aspect ratio
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.screenshot_label.width() - 20,
            self.screenshot_label.height() - 20,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.screenshot_label.setPixmap(scaled_pixmap)

    def _on_item_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        """Handle item selection change in the list (click or keyboard).

        Args:
            current (QListWidgetItem | None): The newly selected item.
            _previous (QListWidgetItem | None): The previously selected item.
        """
        if current is None:
            return

        icon_info: DetectedIconInfo = current.data(Qt.ItemDataRole.UserRole)
        self.selected_icon = icon_info

        # Highlight icon in screenshot
        if self.scan_result:
            self._display_screenshot(self.scan_result.original_image, icon_info)

        # Update comparison panel
        self._update_comparison(icon_info)

    def _update_comparison(self, icon_info: DetectedIconInfo) -> None:
        """Update the comparison panel with detected icon and templates from database.

        Shows: Detected icon | Settings | Separator | All DB templates sorted by NCC

        Args:
            icon_info (DetectedIconInfo): The selected icon information.
        """
        # Preserve current spinbox values before clearing (use fixed defaults otherwise)
        phash_threshold = (
            self.phash_spinbox.value() if self.phash_spinbox else DEFAULT_PHASH_THRESHOLD
        )
        max_ncc_candidates = (
            self.ncc_spinbox.value() if self.ncc_spinbox else DEFAULT_MAX_NCC_CANDIDATES
        )

        self._clear_comparison()

        if not self.all_databases or not self.scan_result:
            return

        # Get resolution and database
        screenshot_res = self._get_screenshot_resolution()
        if not screenshot_res or screenshot_res not in self.all_databases:
            return

        screenshot_db = self.all_databases[screenshot_res]
        target_size = screenshot_db.templates[0].image.shape[0] if screenshot_db.templates else 64

        # Look up each candidate's template image by identity, for display only.
        template_by_key = {
            (tmpl.code, tmpl.mod, tmpl.crated, str(tmpl.faction)): tmpl
            for tmpl in screenshot_db.templates
        }

        # The engine (fs_ocr.scan_debug) already did the matching; we only filter
        # its candidates by the user's controls (no re-scan needed since each
        # candidate carries its own pHash distance): keep those within the pHash
        # threshold, take the closest max_ncc by pHash distance, then rank by NCC.
        candidates = [c for c in icon_info.candidates if c.phash_distance <= phash_threshold]
        candidates.sort(key=lambda c: c.phash_distance)
        candidates = candidates[:max_ncc_candidates]
        candidates.sort(key=lambda c: c.confidence, reverse=True)

        matched_code = candidates[0].code if candidates else icon_info.code

        # Display detected icon with the engine's matched code
        detected_widget = self._create_icon_display(
            image=icon_info.icon_image,
            label=t("debug_viewer.detected"),
            sublabel=matched_code,
            ncc_score=None,
            target_size=target_size,
        )
        self.comparison_layout.addWidget(detected_widget)

        # Add settings widget (pHash threshold and max NCC candidates)
        settings_widget = self._create_settings_widget(phash_threshold, max_ncc_candidates)
        self.comparison_layout.addWidget(settings_widget)

        # Add separator
        self._add_separator()

        # Display candidate templates ranked by NCC (the engine's scores)
        for candidate in candidates:
            template = template_by_key.get(
                (candidate.code, candidate.mod, candidate.crated, candidate.faction)
            )
            if template is None:
                logger.debug("No template image for candidate %s/%s", candidate.mod, candidate.code)
                continue
            template_widget = self._create_icon_display(
                image=template.image,
                label=candidate.mod,
                sublabel=candidate.code,
                ncc_score=candidate.confidence,
                target_size=target_size,
            )
            self.comparison_layout.addWidget(template_widget)

        self.comparison_layout.addStretch()

    def _create_settings_widget(
        self, phash_value: int | None = None, ncc_value: int | None = None
    ) -> QWidget:
        """Create a widget with pHash and NCC settings spinboxes.

        Args:
            phash_value (int | None): Initial pHash threshold value. Uses the default if None.
            ncc_value (int | None): Initial max NCC candidates value. Uses the default if None.

        Returns:
            QWidget: Widget containing the settings controls.
        """
        # Use the fixed matching defaults when no explicit value is provided
        if phash_value is None:
            phash_value = DEFAULT_PHASH_THRESHOLD
        if ncc_value is None:
            ncc_value = DEFAULT_MAX_NCC_CANDIDATES
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # pHash threshold
        phash_label = QLabel("pHash threshold:")
        phash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(phash_label)

        self.phash_spinbox = QSpinBox()
        self.phash_spinbox.setRange(0, 64)
        self.phash_spinbox.setValue(phash_value)
        self.phash_spinbox.setFixedWidth(80)
        self.phash_spinbox.valueChanged.connect(self._on_settings_changed)
        layout.addWidget(self.phash_spinbox, alignment=Qt.AlignmentFlag.AlignCenter)

        # Max NCC candidates
        ncc_label = QLabel("Max NCC candidates:")
        ncc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ncc_label)

        self.ncc_spinbox = QSpinBox()
        self.ncc_spinbox.setRange(1, 100)
        self.ncc_spinbox.setValue(ncc_value)
        self.ncc_spinbox.setFixedWidth(80)
        self.ncc_spinbox.valueChanged.connect(self._on_settings_changed)
        layout.addWidget(self.ncc_spinbox, alignment=Qt.AlignmentFlag.AlignCenter)

        return widget

    def _on_settings_changed(self) -> None:
        """Handle settings change - re-run matching with new thresholds."""
        if not self.selected_icon or not self.scan_result:
            return

        # Re-run comparison with current settings
        self._update_comparison(self.selected_icon)

    def _get_screenshot_resolution(self) -> SupportedResolution | None:
        """Get the SupportedResolution matching the screenshot.

        Returns:
            SupportedResolution | None: Matching resolution or None if not found.
        """
        if not self.scan_result or not self.scan_result.stockpile.resolution:
            return None

        # Resolution is like "1920x1080", extract height
        try:
            height_str = self.scan_result.stockpile.resolution.split("x")[1]
            height = int(height_str)

            # Find matching SupportedResolution
            for res in SupportedResolution:
                if int(res.value) == height:
                    return res
        except (IndexError, ValueError):
            pass

        return None

    def _add_separator(self) -> None:
        """Add a vertical separator to the comparison layout."""
        separator = QWidget()
        separator.setFixedWidth(2)
        separator.setStyleSheet("background-color: palette(mid);")
        self.comparison_layout.addWidget(separator)

    def _create_icon_display(
        self,
        image: np.ndarray,
        label: str,
        sublabel: str | None,
        ncc_score: float | None,
        target_size: int,
    ) -> QWidget:
        """Create a widget displaying an icon with label and optional NCC score.

        Args:
            image (np.ndarray): Image to display (BGR format).
            label (str): Label text (e.g., mod name or "Detected").
            sublabel (str | None): Second line label text (e.g., code name or pHash dist).
            ncc_score (float | None): NCC score to display, or None for detected icon.
            target_size (int): Target size for scaling.

        Returns:
            QWidget: Widget containing the icon display.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Scale image to 4x for visibility
        scale = 4
        scaled_size = target_size * scale

        # Resize image if needed to match target size first
        if image.shape[0] != target_size or image.shape[1] != target_size:
            image = resize_bgr(image, target_size, target_size, mode="area")

        # Scale up for display
        display_image = resize_bgr(image, scaled_size, scaled_size, mode="nearest")

        # Convert BGR to RGB for Qt
        rgb_image = swap_rb(display_image)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        qt_image = QImage(
            rgb_image.data.tobytes(),
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qt_image)

        # Icon image
        image_label = QLabel()
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("QLabel { border: 1px solid palette(mid); }")
        layout.addWidget(image_label)

        # Label text (line 1)
        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(text_label)

        # Sublabel (line 2)
        if sublabel:
            sublabel_widget = QLabel(sublabel)
            sublabel_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sublabel_widget.setStyleSheet("QLabel { color: palette(mid); }")
            layout.addWidget(sublabel_widget)

        # NCC score (line 3) - add spacer if None to keep alignment
        score_label = QLabel()
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if ncc_score is not None:
            score_label.setText(f"NCC: {ncc_score:.3f}")
            # Color based on score
            if ncc_score >= 0.95:
                color = "#4caf50"  # Green
            elif ncc_score >= 0.90:
                color = "#ff9800"  # Orange
            else:
                color = "#f44336"  # Red
            score_label.setStyleSheet(f"QLabel {{ color: {color}; }}")
        else:
            score_label.setText(" ")  # Spacer for alignment
        layout.addWidget(score_label)

        return widget

    def _clear_comparison(self) -> None:
        """Clear the comparison panel."""
        # Reset spinbox references before deleting widgets
        self.phash_spinbox = None
        self.ncc_spinbox = None

        while self.comparison_layout.count():
            child = self.comparison_layout.takeAt(0)
            if child is not None:
                widget = child.widget()
                if widget is not None:
                    widget.deleteLater()

    def load_databases(self) -> None:
        """Load all template databases in background thread."""
        if not self.database_path:
            return

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

    def _on_database_error(self, error_msg: str) -> None:
        """Handle database loading error.

        Args:
            error_msg (str): Error message.
        """
        logger.error("Failed to load database: %s", error_msg)
        QMessageBox.warning(
            self,
            t("debug_viewer.database_error_title"),
            error_msg,
        )

    def resizeEvent(self, event: object) -> None:
        """Handle window resize event to update screenshot display.

        Args:
            event (object): Resize event.
        """
        super().resizeEvent(event)  # type: ignore[arg-type]

        # Re-display screenshot if we have one
        if self.scan_result and self.scan_result.original_image is not None:
            self._display_screenshot(self.scan_result.original_image, self.selected_icon)

    def closeEvent(self, event: object) -> None:
        """Handle window close event.

        Args:
            event (object): Close event.
        """
        # Wait for threads to finish if running
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.wait()
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.wait()

        if hasattr(event, "accept"):
            event.accept()
