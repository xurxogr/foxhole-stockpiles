"""Output settings tab."""

from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.output import (
    FileHandlerSettings,
    OutputHandlerConfig,
    OutputSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.gui.widgets.config_tabs.output_handler_dialog import OutputHandlerDialog
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class OutputTab(QWidget):
    """Tab for Output configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the Output tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self._handlers: list[OutputHandlerConfig] = []
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Description
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("QLabel { color: gray; margin-bottom: 10px; }")
        layout.addWidget(self.description_label)

        # Handlers group
        self.handlers_group = QGroupBox()
        handlers_layout = QVBoxLayout()
        self.handlers_group.setLayout(handlers_layout)

        # List widget
        self.handlers_list = QListWidget()
        self.handlers_list.setMinimumHeight(150)
        self.handlers_list.itemDoubleClicked.connect(self._on_edit_clicked)
        self.handlers_list.itemSelectionChanged.connect(self._update_buttons_state)
        handlers_layout.addWidget(self.handlers_list)

        # Buttons row 1: Add, Edit, Remove
        buttons_layout = QHBoxLayout()

        self.add_button = QPushButton()
        self.add_button.clicked.connect(self._on_add_clicked)
        buttons_layout.addWidget(self.add_button)

        self.edit_button = QPushButton()
        self.edit_button.clicked.connect(self._on_edit_clicked)
        buttons_layout.addWidget(self.edit_button)

        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(self._on_remove_clicked)
        buttons_layout.addWidget(self.remove_button)

        buttons_layout.addStretch()

        # Reorder buttons
        self.move_up_button = QPushButton()
        self.move_up_button.clicked.connect(self._on_move_up_clicked)
        buttons_layout.addWidget(self.move_up_button)

        self.move_down_button = QPushButton()
        self.move_down_button.clicked.connect(self._on_move_down_clicked)
        buttons_layout.addWidget(self.move_down_button)

        handlers_layout.addLayout(buttons_layout)

        # Order info label
        self.order_info_label = QLabel()
        self.order_info_label.setWordWrap(True)
        self.order_info_label.setStyleSheet(
            "QLabel { "
            "color: #2196F3; "
            "font-size: 11px; "
            "padding: 5px; "
            "background-color: palette(alternate-base); "
            "border: 1px solid #2196F3; "
            "border-radius: 3px; "
            "}"
        )
        handlers_layout.addWidget(self.order_info_label)

        layout.addWidget(self.handlers_group)
        layout.addStretch()

        # Apply translations
        self.retranslate()

        # Initial state
        self._update_buttons_state()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.description_label.setText(t("output_tab.description"))
        self.handlers_group.setTitle(t("output_tab.handlers_group"))

        self.add_button.setText(t("common.add"))
        self.add_button.setToolTip(t("output_tab.handler_dialog.name_tooltip"))
        self.edit_button.setText(t("common.edit"))
        self.remove_button.setText(t("common.remove"))

        self.move_up_button.setText(t("output_tab.move_up"))
        self.move_up_button.setToolTip(t("output_tab.move_up_tooltip"))
        self.move_down_button.setText(t("output_tab.move_down"))
        self.move_down_button.setToolTip(t("output_tab.move_down_tooltip"))

        self.order_info_label.setText("ℹ️ " + t("output_tab.order_info"))

    def _update_buttons_state(self) -> None:
        """Update button enabled states based on selection."""
        row = self.handlers_list.currentRow()
        has_selection = row >= 0
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)
        self.move_up_button.setEnabled(has_selection and row > 0)
        self.move_down_button.setEnabled(has_selection and row < len(self._handlers) - 1)

    def _update_list(self) -> None:
        """Update the handlers list widget."""
        self.handlers_list.clear()
        for handler_config in self._handlers:
            handler = handler_config.handler
            handler_type = handler.type
            format_type = handler_config.format.type
            if isinstance(format_type, OutputFormat):
                format_str = format_type.value.upper()
            else:
                format_str = str(format_type).upper()
            item_text = f"{handler_config.name} ({handler_type})"

            # Add extra info based on type
            if isinstance(handler, FileHandlerSettings):
                item_text = f"{handler_config.name} [{format_str}] - {handler.path}"
            elif isinstance(handler, WebhookHandlerSettings):
                url = handler.url or ""
                truncated_url = url[:40] + "..." if len(url) > 40 else url
                item_text = f"{handler_config.name} [{format_str}] - {truncated_url}"

            item = QListWidgetItem(item_text)
            item.setToolTip(f"Type: {handler_type}, Format: {format_str}")
            self.handlers_list.addItem(item)
        self._update_buttons_state()

    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        dialog = OutputHandlerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            handler_config = dialog.get_handler_config()
            self._handlers.append(handler_config)
            self._update_list()
            # Select the new item
            self.handlers_list.setCurrentRow(len(self._handlers) - 1)

    def _on_edit_clicked(self) -> None:
        """Handle edit button click."""
        row = self.handlers_list.currentRow()
        if row < 0:
            return

        handler_config = self._handlers[row]
        dialog = OutputHandlerDialog(self, handler_config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._handlers[row] = dialog.get_handler_config()
            self._update_list()
            self.handlers_list.setCurrentRow(row)

    def _on_remove_clicked(self) -> None:
        """Handle remove button click."""
        row = self.handlers_list.currentRow()
        if row < 0:
            return

        handler_config = self._handlers[row]
        message = t("output_tab.remove_handler_message").replace("{name}", handler_config.name)
        reply = QMessageBox.question(
            self,
            t("output_tab.remove_handler_title"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self._handlers[row]
            self._update_list()

    def _on_move_up_clicked(self) -> None:
        """Handle move up button click."""
        row = self.handlers_list.currentRow()
        if row <= 0:
            return

        # Swap with previous item
        self._handlers[row], self._handlers[row - 1] = (
            self._handlers[row - 1],
            self._handlers[row],
        )
        self._update_list()
        self.handlers_list.setCurrentRow(row - 1)

    def _on_move_down_clicked(self) -> None:
        """Handle move down button click."""
        row = self.handlers_list.currentRow()
        if row < 0 or row >= len(self._handlers) - 1:
            return

        # Swap with next item
        self._handlers[row], self._handlers[row + 1] = (
            self._handlers[row + 1],
            self._handlers[row],
        )
        self._update_list()
        self.handlers_list.setCurrentRow(row + 1)

    def set_values(self, settings: OutputSettings) -> None:
        """Set widget values from settings.

        Args:
            settings (OutputSettings): OutputSettings instance to load values from.
        """
        self._handlers = list(settings.handlers)
        self._update_list()

    def get_values(self) -> OutputSettings:
        """Get current values from widgets.

        Returns:
            OutputSettings: OutputSettings instance with current values from widgets
        """
        return OutputSettings(handlers=list(self._handlers))
