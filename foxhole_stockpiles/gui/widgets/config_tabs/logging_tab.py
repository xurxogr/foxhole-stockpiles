"""Logging settings tab."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.logging import LoggingSettings
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class CustomLoggerRowWidget(QWidget):
    """Widget for a custom logger entry with name, level dropdown, and remove button."""

    def __init__(
        self,
        logger_name: str,
        level: str,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the custom logger row widget.

        Args:
            logger_name: Name of the logger
            level: Log level for this logger
            parent: Parent widget
        """
        super().__init__(parent)
        self._removed = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Logger name input
        self.name_input = QLineEdit(logger_name)
        self.name_input.setPlaceholderText(t("logging_tab.logger_placeholder"))
        layout.addWidget(self.name_input, 1)  # stretch factor 1

        # Level dropdown
        self.level_combo = QComboBox()
        self.level_combo.addItems(LOG_LEVELS)
        self.level_combo.setCurrentText(level.upper())
        self.level_combo.setFixedWidth(100)
        layout.addWidget(self.level_combo)

        # Remove button
        self.remove_btn = QPushButton(t("common.remove"))
        self.remove_btn.setFixedWidth(80)
        self.remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(self.remove_btn)

    def _on_remove(self) -> None:
        """Handle remove button click."""
        self._removed = True
        self.setVisible(False)

    def is_removed(self) -> bool:
        """Check if this row was removed."""
        return self._removed

    def get_logger_name(self) -> str:
        """Get the logger name."""
        return self.name_input.text().strip()

    def get_level(self) -> str:
        """Get the selected log level."""
        return self.level_combo.currentText()


class LoggingTab(QWidget):
    """Tab for Logging configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the Logging tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.custom_logger_rows: list[CustomLoggerRowWidget] = []
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Form section for basic settings
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)

        # Root Log Level
        self.root_level_label = QLabel()
        self.root_level_combo = QComboBox()
        self.root_level_combo.addItems(LOG_LEVELS)
        self.root_level_combo.setCurrentText("INFO")
        form_layout.addRow(self.root_level_label, self.root_level_combo)

        # Log Format
        self._log_format_label = QLabel()
        self.log_format_input = QLineEdit()
        self.log_format_input.setPlaceholderText(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        form_layout.addRow(self._log_format_label, self.log_format_input)

        # Date Format
        self._date_format_label = QLabel()
        self.date_format_input = QLineEdit()
        self.date_format_input.setPlaceholderText("%Y-%m-%d %H:%M:%S")
        form_layout.addRow(self._date_format_label, self.date_format_input)

        # Rotate Logs
        self._rotate_logs_label = QLabel()
        self.rotate_logs_input = QCheckBox()
        form_layout.addRow(self._rotate_logs_label, self.rotate_logs_input)

        # Log File
        self._log_file_label = QLabel()
        self._log_file_widget = QWidget()
        log_file_layout = QHBoxLayout(self._log_file_widget)
        log_file_layout.setContentsMargins(0, 0, 0, 0)
        self.log_file_input = QLineEdit()
        self.log_browse = QPushButton()
        self.log_browse.clicked.connect(self._browse_log_file)
        log_file_layout.addWidget(self.log_file_input)
        log_file_layout.addWidget(self.log_browse)
        form_layout.addRow(self._log_file_label, self._log_file_widget)

        layout.addLayout(form_layout)

        # Custom Log Levels header with Add button
        self._custom_loggers_header = QWidget()
        header_layout = QHBoxLayout(self._custom_loggers_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_loggers_label = QLabel()
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self._on_add_logger)
        header_layout.addWidget(self.custom_loggers_label)
        header_layout.addStretch()
        header_layout.addWidget(self.add_btn)
        layout.addWidget(self._custom_loggers_header)

        # Scroll area for custom logger rows (expands to fill remaining space)
        self._loggers_scroll = QScrollArea()
        self._loggers_scroll.setWidgetResizable(True)

        self.loggers_container = QWidget()
        self.loggers_list_layout = QVBoxLayout(self.loggers_container)
        self.loggers_list_layout.setContentsMargins(0, 0, 0, 0)
        self.loggers_list_layout.setSpacing(4)
        self.loggers_list_layout.addStretch()

        self._loggers_scroll.setWidget(self.loggers_container)
        layout.addWidget(self._loggers_scroll, 1)  # stretch factor 1 to fill space

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
        self.root_level_label.setText(t("logging_tab.root_level"))
        self.root_level_label.setToolTip(t("logging_tab.root_level_tooltip"))

        self._log_format_label.setText(t("logging_tab.log_format"))
        self._log_format_label.setToolTip(t("logging_tab.log_format_tooltip"))

        self._date_format_label.setText(t("logging_tab.date_format"))
        self._date_format_label.setToolTip(t("logging_tab.date_format_tooltip"))

        self._rotate_logs_label.setText(t("logging_tab.rotate_logs"))
        self._rotate_logs_label.setToolTip(t("logging_tab.rotate_logs_tooltip"))
        self.rotate_logs_input.setText(t("logging_tab.rotate_logs_checkbox"))

        self._log_file_label.setText(t("logging_tab.log_file"))
        self._log_file_label.setToolTip(t("logging_tab.log_file_tooltip"))
        self.log_file_input.setPlaceholderText(t("logging_tab.log_file_placeholder"))
        self.log_browse.setText(t("common.browse"))

        self.custom_loggers_label.setText(t("logging_tab.custom_loggers"))
        self.custom_loggers_label.setToolTip(t("logging_tab.custom_loggers_tooltip"))
        self.add_btn.setText(t("common.add"))

    def _add_custom_logger_row(self, logger_name: str, level: str) -> CustomLoggerRowWidget:
        """Add a custom logger row to the list.

        Args:
            logger_name: Name of the logger
            level: Log level

        Returns:
            The created CustomLoggerRowWidget
        """
        row = CustomLoggerRowWidget(logger_name, level)
        self.custom_logger_rows.append(row)
        # Insert before the stretch
        self.loggers_list_layout.insertWidget(self.loggers_list_layout.count() - 1, row)
        return row

    def _on_add_logger(self) -> None:
        """Handle add logger button click."""
        self._add_custom_logger_row("", "INFO")

    def _browse_log_file(self) -> None:
        """Open file dialog for log file path."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            t("logging_tab.select_log_file"),
            "",
            "Log Files (*.log);;All Files (*)",
        )
        if filepath:
            self.log_file_input.setText(filepath)

    def _clear_custom_logger_rows(self) -> None:
        """Clear all custom logger rows (for reloading)."""
        for row in self.custom_logger_rows:
            row.setParent(None)
            row.deleteLater()
        self.custom_logger_rows.clear()

    def set_values(self, settings: LoggingSettings) -> None:
        """Set widget values from settings.

        Args:
            settings (LoggingSettings): LoggingSettings instance to load values from.
        """
        # Set root log level
        self.root_level_combo.setCurrentText(settings.log_level.upper())

        # Set other values
        self.log_format_input.setText(settings.log_format)
        self.date_format_input.setText(settings.date_format)
        self.rotate_logs_input.setChecked(settings.rotate_logs)
        self.log_file_input.setText(str(settings.log_file) if settings.log_file else "")

        # Clear existing custom logger rows and recreate
        self._clear_custom_logger_rows()

        # Add custom loggers from settings
        for logger_name, level in settings.loggers.items():
            self._add_custom_logger_row(logger_name, level)

    def get_values(self) -> LoggingSettings:
        """Get current values from widgets.

        Returns:
            LoggingSettings: LoggingSettings instance with current values from widgets
        """
        # Get root log level
        log_level = self.root_level_combo.currentText()

        # Collect custom logger levels
        loggers: dict[str, str] = {}
        for row in self.custom_logger_rows:
            if row.is_removed():
                continue

            name = row.get_logger_name()
            level = row.get_level()

            if not name:
                continue

            loggers[name] = level

        return LoggingSettings(
            log_level=log_level,
            loggers=loggers,
            log_format=self.log_format_input.text(),
            date_format=self.date_format_input.text(),
            rotate_logs=self.rotate_logs_input.isChecked(),
            log_file=self.log_file_input.text() or None,
        )
