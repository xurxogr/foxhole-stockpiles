"""Main window for the fs-tools desktop application.

Acts as a launcher: each tool opens its own window/dialog, reusing the
windows that previously lived in the main ``fs`` application.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles import __version__
from foxhole_stockpiles.core.settings import reload_settings
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from fs_tools.gui.widgets.tool_launcher_row import ToolLauncherRow
from fs_tools.gui.windows.catalog_builder_window import CatalogBuilderWindow
from fs_tools.gui.windows.database_info_window import DatabaseInfoWindow
from fs_tools.gui.windows.database_visualizer_window import DatabaseVisualizerWindow
from fs_tools.gui.windows.debug_image_window import DebugImageWindow
from fs_tools.gui.windows.icon_import_window import IconImportWindow
from fs_tools.gui.windows.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class ToolsMainWindow(QMainWindow):
    """Launcher window for the Foxhole Stockpiles database tools."""

    def __init__(self) -> None:
        """Initialize the tools launcher window."""
        super().__init__()
        self.setGeometry(150, 150, 540, 500)

        # Keep references so launched windows are not garbage-collected.
        self._open_windows: list[QWidget] = []

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        # Build tools: produce or update the catalog and template database.
        self._build_section_label = self._make_section_label()
        layout.addWidget(self._build_section_label)

        self._catalog_builder_row = ToolLauncherRow(
            self._tool_icon(QStyle.StandardPixmap.SP_FileIcon)
        )
        self._catalog_builder_row.clicked.connect(self.show_catalog_builder)
        layout.addWidget(self._catalog_builder_row)

        self._icon_import_row = ToolLauncherRow(
            self._tool_icon(QStyle.StandardPixmap.SP_DriveHDIcon)
        )
        self._icon_import_row.clicked.connect(self.show_icon_import)
        layout.addWidget(self._icon_import_row)

        # Inspect tools: browse and debug the existing template database.
        self._inspect_section_label = self._make_section_label()
        layout.addSpacing(8)
        layout.addWidget(self._inspect_section_label)

        self._visualizer_row = ToolLauncherRow(
            self._tool_icon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self._visualizer_row.clicked.connect(self.show_database_visualizer)
        layout.addWidget(self._visualizer_row)

        self._debug_viewer_row = ToolLauncherRow(
            self._tool_icon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self._debug_viewer_row.clicked.connect(self.show_debug_viewer)
        layout.addWidget(self._debug_viewer_row)

        self._database_info_row = ToolLauncherRow(
            self._tool_icon(QStyle.StandardPixmap.SP_FileDialogInfoView)
        )
        self._database_info_row.clicked.connect(self.show_database_info)
        layout.addWidget(self._database_info_row)

        layout.addStretch(1)

        self.setCentralWidget(central)

        # Configuration lives in the menu bar, not the tool button column.
        self._create_menu_bar()

        # Apply translations.
        self.retranslate()

        # Enable only the tools whose required configuration is present.
        self._refresh_tool_availability()

        # Connect to language change signal with cleanup.
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle a language change event.

        Args:
            _language (str): The newly selected language code (unused).
        """
        self.retranslate()

    def _make_section_label(self) -> QLabel:
        """Create a bold section header label for the launcher.

        Returns:
            QLabel: A label styled as a section header.
        """
        label = QLabel()
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _tool_icon(self, pixmap: QStyle.StandardPixmap) -> QIcon:
        """Return a standard style icon for a launcher row.

        Args:
            pixmap (QStyle.StandardPixmap): The standard pixmap to render.

        Returns:
            QIcon: The icon drawn from the current widget style.
        """
        return self.style().standardIcon(pixmap)

    def _create_menu_bar(self) -> None:
        """Create the launcher menu bar with the configuration entry."""
        menu_bar = self.menuBar()

        self._file_menu = menu_bar.addMenu("")

        self._configuration_action = QAction(self)
        self._configuration_action.triggered.connect(self.show_settings)
        self._file_menu.addAction(self._configuration_action)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("tools_window.title", version=__version__))
        self._file_menu.setTitle(t("tools_window.menu.file"))
        self._configuration_action.setText(t("tools_window.buttons.configuration"))
        self._build_section_label.setText(t("tools_window.sections.build"))
        self._inspect_section_label.setText(t("tools_window.sections.inspect"))
        self._catalog_builder_row.set_text(
            t("tools_window.buttons.catalog_builder"),
            t("tools_window.descriptions.catalog_builder"),
        )
        self._icon_import_row.set_text(
            t("tools_window.buttons.icon_import"),
            t("tools_window.descriptions.icon_import"),
        )
        self._visualizer_row.set_text(
            t("tools_window.buttons.visualizer"),
            t("tools_window.descriptions.visualizer"),
        )
        self._debug_viewer_row.set_text(
            t("tools_window.buttons.debug_viewer"),
            t("tools_window.descriptions.debug_viewer"),
        )
        self._database_info_row.set_text(
            t("tools_window.buttons.database_info"),
            t("tools_window.descriptions.database_info"),
        )

    def _configured_database_path(self) -> str | None:
        """Return the database path from settings, if configured.

        Returns:
            str | None: Configured database path or None when unavailable.
        """
        try:
            settings = AppSettings()
            if settings.scanner.database_path:
                return str(settings.scanner.database_path)
        except Exception as e:
            logger.warning("Could not read configured database path: %s", e)
        return None

    def _require_database_path(self) -> str | None:
        """Return the configured database path or warn when missing.

        Returns:
            str | None: Configured database path, or None after warning the user.
        """
        database_path = self._configured_database_path()
        if not database_path:
            QMessageBox.warning(
                self,
                t("tools_window.no_database_title"),
                t("tools_window.no_database_message"),
            )
            return None
        return database_path

    def _refresh_tool_availability(self) -> None:
        """Enable each tool row only when its required configuration is present.

        Tools that need external executables or a catalog (catalog builder,
        icon import) and tools that need a template database (visualizer, debug
        viewer) are disabled until those settings are configured, so a tool is
        only reachable once it can actually run. The database info tool has no
        prerequisite and stays enabled.
        """
        try:
            settings = AppSettings()
        except Exception as e:
            logger.warning("Could not read settings for tool availability: %s", e)
            return

        self._catalog_builder_row.set_available(CatalogBuilderWindow.requirements_met(settings))
        self._icon_import_row.set_available(IconImportWindow.requirements_met(settings))

        has_database = bool(settings.scanner.database_path)
        self._visualizer_row.set_available(has_database)
        self._debug_viewer_row.set_available(has_database)

    def _track(self, window: QWidget) -> None:
        """Keep a reference to a launched window.

        Args:
            window (QWidget): The window to retain.
        """
        self._open_windows.append(window)
        window.destroyed.connect(lambda: self._open_windows.remove(window))

    def show_icon_import(self) -> None:
        """Open the icon import / database builder window."""
        window = IconImportWindow(self)
        self._track(window)
        window.show()

    def show_catalog_builder(self) -> None:
        """Open the catalog builder window."""
        window = CatalogBuilderWindow(self)
        self._track(window)
        window.show()

    def show_database_info(self) -> None:
        """Open the database information dialog."""
        window = DatabaseInfoWindow(self, initial_db_path=self._configured_database_path())
        window.setWindowModality(Qt.WindowModality.NonModal)
        self._track(window)
        window.show()

    def show_settings(self) -> None:
        """Open the fs-tools configuration dialog."""
        dialog = SettingsDialog(self)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.exec()

        # Settings may have changed; refresh the cached settings and re-evaluate
        # which tools are now available.
        reload_settings()
        self._refresh_tool_availability()

    def show_database_visualizer(self) -> None:
        """Open the database visualizer dialog."""
        database_path = self._require_database_path()
        if database_path is None:
            return
        window = DatabaseVisualizerWindow(self, database_path=database_path)
        window.setWindowModality(Qt.WindowModality.NonModal)
        self._track(window)
        window.show()

    def show_debug_viewer(self) -> None:
        """Open the debug image viewer dialog."""
        database_path = self._require_database_path()
        if database_path is None:
            return
        window = DebugImageWindow(self, database_path=database_path)
        window.setWindowModality(Qt.WindowModality.NonModal)
        self._track(window)
        window.show()
