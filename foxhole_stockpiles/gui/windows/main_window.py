"""Main application window."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from foxhole_stockpiles import __version__
from foxhole_stockpiles.core.settings.app_settings import AppSettings
from foxhole_stockpiles.enums.config_level import ConfigLevel
from foxhole_stockpiles.enums.sav_mode import SavMode
from foxhole_stockpiles.gui.utils.qt_log_handler import QtLogHandler
from foxhole_stockpiles.gui.widgets.capture_panel import CapturePanel
from foxhole_stockpiles.gui.windows.config_window import ConfigWindow
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        # Load minimize_to_tray preference from config (default: False)
        self.minimize_to_tray = self._load_minimize_to_tray_setting()
        # Track menu actions that should be hidden based on config level
        self._advanced_menu_actions: list[QAction] = []
        self.init_ui()
        self.create_tray_icon()
        # Apply config level to menu visibility
        self._apply_config_level_to_menus()
        # Connect to language changes with cleanup on destruction
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event.

        Args:
            _language: The new language code (unused).
        """
        self.retranslate()

    def _load_minimize_to_tray_setting(self) -> bool:
        """Load minimize_to_tray setting from config.

        Returns:
            bool: The minimize_to_tray setting value
        """
        try:
            settings = AppSettings()
            return settings.gui.minimize_to_tray
        except Exception as e:
            logger.warning(f"Failed to load minimize_to_tray setting: {e}")
            return False

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle(f"FS (Foxhole Stockpiles) - v{__version__}")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget with the capture control panel
        self.capture_panel = CapturePanel()
        self.setCentralWidget(self.capture_panel)

        # Create menu bar
        self.create_menu_bar()

    def create_menu_bar(self) -> None:
        """Create the menu bar."""
        menu_bar = self.menuBar()

        # File menu
        self.file_menu = menu_bar.addMenu("")

        self.config_action = self.file_menu.addAction("")
        self.config_action.triggered.connect(self.show_configuration)

        self.scan_action = self.file_menu.addAction("")
        self.scan_action.triggered.connect(self.scan_screenshot)

        self.scan_sav_action = self.file_menu.addAction("")
        self.scan_sav_action.triggered.connect(self.scan_sav)

        self.file_menu.addSeparator()

        self.exit_action = self.file_menu.addAction("")
        self.exit_action.triggered.connect(self.quit_application)

        # Database/template tooling lives in the separate 'fs-tools' app.

        # Help menu
        self.help_menu = menu_bar.addMenu("")
        self.about_action = self.help_menu.addAction("")
        self.about_action.triggered.connect(self.show_about)

        # Apply initial translations
        self.retranslate()

        # Disable the manual-scan action when SAV monitor mode is configured.
        self._apply_sav_menu_state()

    def _apply_config_level_to_menus(self) -> None:
        """Apply config level settings to menu visibility."""
        try:
            settings = AppSettings()
            config_level = settings.gui.config_level
            # Advanced menu actions are visible at advanced and developer levels
            for action in self._advanced_menu_actions:
                action.setVisible(config_level.is_at_least(ConfigLevel.ADVANCED))
        except Exception as e:
            logger.warning(f"Failed to apply config level to menus: {e}")

    def _create_fs_icon(self) -> QIcon:
        """Create a simple FS icon for the system tray.

        Returns:
            QIcon: Icon with "FS" text on blue background.
        """
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 120, 215))

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "FS")
        painter.end()

        return QIcon(pixmap)

    def create_tray_icon(self) -> None:
        """Create system tray icon with menu."""
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this system")
            self.minimize_to_tray = False
            return

        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._create_fs_icon())

        # Create tray menu
        tray_menu = QMenu()

        self.tray_show_action = QAction("", self)
        self.tray_show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(self.tray_show_action)

        self.tray_hide_action = QAction("", self)
        self.tray_hide_action.triggered.connect(self.hide)
        tray_menu.addAction(self.tray_hide_action)

        tray_menu.addSeparator()

        self.tray_config_action = QAction("", self)
        self.tray_config_action.triggered.connect(self.show_configuration)
        tray_menu.addAction(self.tray_config_action)

        tray_menu.addSeparator()

        self.tray_quit_action = QAction("", self)
        self.tray_quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(self.tray_quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Apply translations to tray menu
        self._retranslate_tray()

        # Double-click to show window
        self.tray_icon.activated.connect(self.tray_icon_activated)

        # Set tooltip
        self.tray_icon.setToolTip(f"FS (Foxhole Stockpiles) - v{__version__}")

        self.tray_icon.show()

    def tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation.

        Args:
            reason (QSystemTrayIcon.ActivationReason): Activation reason
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self) -> None:
        """Show window from system tray."""
        self.show()
        self.activateWindow()
        self.raise_()

    def scan_screenshot(self) -> None:
        """Open file dialog to scan a screenshot."""
        self.capture_panel.scan_screenshot_from_menu()

    def scan_sav(self) -> None:
        """Scan the configured SAV file once."""
        self.capture_panel.scan_sav_from_menu()

    def show_configuration(self) -> None:
        """Show configuration window as modal dialog centered on main window."""
        config_window = ConfigWindow(self)
        config_window.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Center the config window on the main window
        main_geometry = self.geometry()
        config_geometry = config_window.geometry()

        center_x = main_geometry.x() + (main_geometry.width() - config_geometry.width()) // 2
        center_y = main_geometry.y() + (main_geometry.height() - config_geometry.height()) // 2

        config_window.move(center_x, center_y)

        # Connect to refresh DB info and settings when config window closes
        config_window.closed.connect(self.capture_panel.refresh_db_info)
        config_window.closed.connect(self._on_config_closed)

        config_window.show()

    def _on_config_closed(self) -> None:
        """Handle config window closed - refresh settings from config."""
        # Reload minimize_to_tray setting
        self.minimize_to_tray = self._load_minimize_to_tray_setting()
        # Refresh menu visibility based on config level
        self._apply_config_level_to_menus()
        # The SAV mode may have changed; enable the manual-scan action accordingly.
        self._apply_sav_menu_state()
        logger.info(f"Config reloaded - minimize_to_tray: {self.minimize_to_tray}")

    def _apply_sav_menu_state(self) -> None:
        """Enable File → Scan SAV only in manual mode (disabled while monitoring)."""
        try:
            is_manual = AppSettings().sav_processing.mode == SavMode.MANUAL
        except Exception as e:
            logger.warning(f"Failed to read SAV mode: {e}")
            is_manual = True
        self.scan_sav_action.setEnabled(is_manual)

    def show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            t("about.title"),
            f"<h2>{t('about.app_name')}</h2>"
            f"<p>{t('about.version').replace('{version}', __version__)}</p>"
            f"<p>{t('about.description')}</p>"
            f"<p><b>{t('about.features_title')}</b></p>"
            f"<ul>"
            f"<li>{t('about.feature_scanning')}</li>"
            f"<li>{t('about.feature_database')}</li>"
            f"<li>{t('about.feature_capture')}</li>"
            f"</ul>"
            f"<p><b>{t('about.links_title')}</b></p>"
            f"<p><a href='https://github.com/xurxogr/foxhole-stockpiles'>{t('about.github_link')}</a></p>"
            f"<p><a href='https://github.com/xurxogr/foxhole-stockpiles-client'>"
            f"{t('about.client_link')}</a></p>"
            f"<hr>"
            f"<p>{t('about.copyright')}</p>"
            f"<p>{t('about.license')}</p>",
        )

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Handle window close event.

        If minimize to tray is enabled, hide to tray instead of closing.
        Otherwise, perform cleanup and close.

        Args:
            event (QCloseEvent | None): Close event
        """
        if not event:
            return

        # Check if we can minimize to tray
        can_minimize_to_tray = (
            self.minimize_to_tray
            and hasattr(self, "tray_icon")
            and self.tray_icon is not None
            and self.tray_icon.isVisible()
        )

        if can_minimize_to_tray:
            logger.info("Minimizing to system tray")
            event.ignore()
            self.hide()
        else:
            # Can't minimize to tray or it's disabled - actually quit
            if self.minimize_to_tray and not can_minimize_to_tray:
                logger.warning(
                    "Cannot minimize to tray (tray icon not available). Quitting instead."
                )
            self.quit_application()
            event.accept()

    def quit_application(self) -> None:
        """Quit the application with proper cleanup."""
        logger.info("Quitting application")

        # Stop capture if running
        if hasattr(self, "capture_panel") and self.capture_panel.capturing:
            logger.info("Stopping capture before quit")
            self.capture_panel.stop_capture()

        # Stop SAV / scan workers if running
        if hasattr(self, "capture_panel"):
            self.capture_panel._stop_all_workers()

        # Remove all QtLogHandler instances from all loggers before Qt cleanup
        root_logger = logging.getLogger()
        handlers_to_remove = [h for h in root_logger.handlers[:] if isinstance(h, QtLogHandler)]

        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
            handler.close()

        # Hide tray icon
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()

        # Close the application
        QApplication.quit()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        # Window title
        self.setWindowTitle(t("main_window.title", version=__version__))

        # File menu
        self.file_menu.setTitle(t("main_window.menu.file"))
        self.config_action.setText(t("main_window.menu.configuration"))
        self.scan_action.setText(t("main_window.menu.scan_screenshot"))
        self.scan_sav_action.setText(t("main_window.menu.scan_sav"))
        self.exit_action.setText(t("main_window.menu.exit"))

        # Help menu
        self.help_menu.setTitle(t("main_window.menu.help"))
        self.about_action.setText(t("main_window.menu.about"))

        # Tray menu (if available)
        self._retranslate_tray()

    def _retranslate_tray(self) -> None:
        """Update tray menu translations."""
        if hasattr(self, "tray_show_action"):
            self.tray_show_action.setText(t("main_window.tray.show"))
            self.tray_hide_action.setText(t("main_window.tray.hide"))
            self.tray_config_action.setText(t("main_window.tray.configuration"))
            self.tray_quit_action.setText(t("main_window.tray.quit"))
        if hasattr(self, "tray_icon"):
            self.tray_icon.setToolTip(t("main_window.title", version=__version__))
