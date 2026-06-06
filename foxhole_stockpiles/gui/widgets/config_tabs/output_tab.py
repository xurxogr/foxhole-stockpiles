"""Output settings tab."""

import os
import re

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    CsvFormatSettings,
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    ReturnHandlerSettings,
    SheetsHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class OutputHandlerDialog(QDialog):
    """Dialog for adding or editing an output handler."""

    def __init__(
        self,
        parent: QWidget | None = None,
        handler_config: OutputHandlerConfig | None = None,
    ) -> None:
        """Initialize the output handler dialog.

        Args:
            parent: Parent widget.
            handler_config: Existing handler config to edit, or None for new handler.
        """
        super().__init__(parent)
        self.handler_config = handler_config
        self.init_ui()
        if handler_config:
            self.load_handler(handler_config)

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Basic settings
        self.basic_group = QGroupBox()
        basic_layout = QFormLayout()
        self.basic_group.setLayout(basic_layout)

        self.name_label = QLabel()
        self.name_input = QLineEdit()
        basic_layout.addRow(self.name_label, self.name_input)

        self.handler_type_label = QLabel()
        self.handler_type_input = QComboBox()
        self.handler_type_input.addItems(["return", "file", "webhook", "console", "google sheets"])
        self.handler_type_input.currentTextChanged.connect(self._on_handler_type_changed)
        basic_layout.addRow(self.handler_type_label, self.handler_type_input)

        self.format_label = QLabel()
        self.format_input = QComboBox()
        self.format_input.addItems(["json", "csv", "tsv"])
        basic_layout.addRow(self.format_label, self.format_input)

        layout.addWidget(self.basic_group)

        # File Settings Group
        self.file_group = QGroupBox()
        file_layout = QFormLayout()
        self.file_group.setLayout(file_layout)

        self.file_path_label = QLabel()
        file_path_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_browse_btn = QPushButton()
        self.file_browse_btn.clicked.connect(self._browse_file)
        file_path_layout.addWidget(self.file_path_input)
        file_path_layout.addWidget(self.file_browse_btn)
        file_layout.addRow(self.file_path_label, file_path_layout)

        layout.addWidget(self.file_group)

        # Webhook Settings Group
        self.webhook_group = QGroupBox()
        webhook_layout = QFormLayout()
        self.webhook_group.setLayout(webhook_layout)

        self.webhook_url_label = QLabel()
        self.webhook_url_input = QLineEdit()
        webhook_layout.addRow(self.webhook_url_label, self.webhook_url_input)

        self.auth_type_label = QLabel()
        self.webhook_auth_type_input = QComboBox()
        self.webhook_auth_type_input.addItems(["null", "basic", "bearer", "forward"])
        self.webhook_auth_type_input.currentTextChanged.connect(self._on_webhook_auth_changed)
        webhook_layout.addRow(self.auth_type_label, self.webhook_auth_type_input)

        self.auth_token_label = QLabel()
        self.webhook_token_input = QLineEdit()
        self.webhook_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        webhook_layout.addRow(self.auth_token_label, self.webhook_token_input)

        self.client_auth_label = QLabel()
        self.webhook_client_auth_input = QLineEdit()
        webhook_layout.addRow(self.client_auth_label, self.webhook_client_auth_input)

        layout.addWidget(self.webhook_group)

        # Spreadsheet Settings Group
        self.sheets_group = QGroupBox()
        sheets_layout = QFormLayout()
        self.sheets_group.setLayout(sheets_layout)

        self.creds_path_label = QLabel()
        self.creds_path_input = QLineEdit()

        creds_layout_widget = QWidget()
        creds_layout = QHBoxLayout(creds_layout_widget)
        creds_layout.setContentsMargins(0, 0, 0, 0)
        self.creds_browse = QPushButton()
        self.creds_browse.clicked.connect(self.browse_credentials)
        creds_layout.addWidget(self.creds_path_input)
        creds_layout.addWidget(self.creds_browse)
        sheets_layout.addRow(self.creds_path_label, creds_layout_widget)

        self.spreadsheet_url_label = QLabel()
        self.spreadsheet_url_input = QLineEdit()
        sheets_layout.addRow(self.spreadsheet_url_label, self.spreadsheet_url_input)

        self.sheet_id_label = QLabel()
        self.sheet_id_input = QLineEdit()
        sheets_layout.addRow(self.sheet_id_label, self.sheet_id_input)

        self.start_cell_label = QLabel()
        self.start_cell_input = QLineEdit()
        sheets_layout.addRow(self.start_cell_label, self.start_cell_input)

        self.row_format_label = QLabel()
        self.row_format_input = QLineEdit()
        sheets_layout.addRow(self.row_format_label, self.row_format_input)

        layout.addWidget(self.sheets_group)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Apply translations
        self.retranslate()

        # Initially show/hide based on handler type and auth type
        self._on_handler_type_changed()
        self._on_webhook_auth_changed()

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        # Window title
        if self.handler_config:
            self.setWindowTitle(t("output_tab.handler_dialog.title_edit"))
        else:
            self.setWindowTitle(t("output_tab.handler_dialog.title_add"))

        # Basic settings
        self.basic_group.setTitle(t("output_tab.handler_dialog.basic_settings"))
        self.name_label.setText(t("common.name") + ":")
        self.name_input.setPlaceholderText(t("output_tab.handler_dialog.name_placeholder"))
        self.name_input.setToolTip(t("output_tab.handler_dialog.name_tooltip"))
        self.handler_type_label.setText(t("output_tab.handler_dialog.handler_type"))
        self.handler_type_label.setToolTip(t("output_tab.handler_dialog.handler_type_tooltip"))
        self.format_label.setText(t("output_tab.handler_dialog.output_format"))
        self.format_label.setToolTip(t("output_tab.handler_dialog.output_format_tooltip"))

        # File settings
        self.file_group.setTitle(t("output_tab.handler_dialog.file_settings"))
        self.file_path_label.setText(t("output_tab.handler_dialog.file_path"))
        self.file_path_label.setToolTip(t("output_tab.handler_dialog.file_path_tooltip"))
        self.file_path_input.setPlaceholderText(
            t("output_tab.handler_dialog.file_path_placeholder")
        )
        self.file_browse_btn.setText(t("common.browse"))

        # Webhook settings
        self.webhook_group.setTitle(t("output_tab.handler_dialog.webhook_settings"))
        self.webhook_url_label.setText(t("output_tab.handler_dialog.webhook_url"))
        self.webhook_url_label.setToolTip(t("output_tab.handler_dialog.webhook_url_tooltip"))
        self.webhook_url_input.setPlaceholderText(
            t("output_tab.handler_dialog.webhook_url_placeholder")
        )
        self.auth_type_label.setText(t("output_tab.handler_dialog.auth_type"))
        self.auth_type_label.setToolTip(t("output_tab.handler_dialog.auth_type_tooltip"))
        self.auth_token_label.setText(t("output_tab.handler_dialog.auth_token"))
        self.auth_token_label.setToolTip(t("output_tab.handler_dialog.auth_token_tooltip"))
        self.webhook_token_input.setPlaceholderText(
            t("output_tab.handler_dialog.auth_token_placeholder")
        )
        self.client_auth_label.setText(t("output_tab.handler_dialog.client_auth_header"))
        self.client_auth_label.setToolTip(t("output_tab.handler_dialog.client_auth_tooltip"))
        self.webhook_client_auth_input.setPlaceholderText(
            t("output_tab.handler_dialog.client_auth_placeholder")
        )

        # Sheets Settings
        self.creds_path_label.setText(t("output_tab.handler_dialog.creds_path"))
        self.creds_path_input.setPlaceholderText(
            t("output_tab.handler_dialog.creds_path_placeholder")
        )
        self.creds_browse.setText(t("common.browse"))
        self.spreadsheet_url_label.setText(t("output_tab.handler_dialog.spreadsheet_url"))
        self.spreadsheet_url_input.setPlaceholderText(
            t("output_tab.handler_dialog.spreadsheet_url_placeholder")
        )
        self.sheet_id_label.setText(t("output_tab.handler_dialog.sheet_id"))
        self.sheet_id_input.setPlaceholderText(t("output_tab.handler_dialog.sheet_id_placeholder"))

        self.start_cell_label.setText(t("output_tab.handler_dialog.start_cell"))
        self.start_cell_input.setPlaceholderText(
            t("output_tab.handler_dialog.start_cell_placeholder")
        )

        self.row_format_label.setText(t("output_tab.handler_dialog.row_format"))
        self.row_format_input.setPlaceholderText(
            t("output_tab.handler_dialog.row_format_placeholder")
        )
        self.row_format_input.setToolTip(t("output_tab.handler_dialog.row_format_tooltip"))

    def _on_handler_type_changed(self) -> None:
        """Handle handler type change to show/hide relevant sections."""
        handler_type = self.handler_type_input.currentText()
        self.file_group.setVisible(handler_type == "file")
        self.webhook_group.setVisible(handler_type == "webhook")
        self.sheets_group.setVisible(handler_type == "google sheets")
        # Show format selection only for file handler (webhook/return are JSON-only)
        show_format = handler_type == "file"
        self.format_label.setVisible(show_format)
        self.format_input.setVisible(show_format)
        # Force JSON format for non-file handlers
        if not show_format:
            self.format_input.setCurrentText("json")

    def _on_webhook_auth_changed(self) -> None:
        """Handle webhook auth type change to show/hide relevant fields."""
        auth_type = self.webhook_auth_type_input.currentText()

        # Show token fields for basic/bearer, hide for forward/null
        show_token = auth_type in ("basic", "bearer")
        self.auth_token_label.setVisible(show_token)
        self.webhook_token_input.setVisible(show_token)

        # Show client auth header field only for forward
        show_client_auth = auth_type == "forward"
        self.client_auth_label.setVisible(show_client_auth)
        self.webhook_client_auth_input.setVisible(show_client_auth)

    def _browse_file(self) -> None:
        """Open file dialog for output file path."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            t("output_tab.handler_dialog.file_path"),
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if filepath:
            self.file_path_input.setText(filepath)

    def load_handler(self, handler_config: OutputHandlerConfig) -> None:
        """Load handler config settings into the dialog.

        Args:
            handler_config: Handler config to load.
        """
        self.name_input.setText(handler_config.name)
        handler = handler_config.handler
        self.handler_type_input.setCurrentText(handler.type)

        # Load format setting
        format_type = handler_config.format.type
        if isinstance(format_type, OutputFormat):
            self.format_input.setCurrentText(format_type.value)
        else:
            self.format_input.setCurrentText(str(format_type))

        if isinstance(handler, FileHandlerSettings):
            self.file_path_input.setText(handler.path)
        elif isinstance(handler, WebhookHandlerSettings):
            self.webhook_url_input.setText(handler.url or "")
            self.webhook_auth_type_input.setCurrentText(handler.auth_type or "null")
            self.webhook_token_input.setText(handler.token or "")
            self.webhook_client_auth_input.setText(handler.client_auth_header or "")
        elif isinstance(handler, SheetsHandlerSettings):
            self.creds_path_input.setText(handler.creds_path or "")
            self.spreadsheet_url_input.setText(handler.spreadsheet_url or "")
            self.sheet_id_input.setText(handler.sheet_id or "")
            self.start_cell_input.setText(handler.start_cell or "")
            self.row_format_input.setText(handler.row_format or "")

        self._on_handler_type_changed()
        self._on_webhook_auth_changed()

    def _validate_and_accept(self) -> None:
        """Validate input and accept dialog if valid."""
        handler_type = self.handler_type_input.currentText()

        if handler_type == "file":
            path = self.file_path_input.text().strip()
            if not path:
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.file_path_required"),
                )
                self.file_path_input.setFocus()
                return

        elif handler_type == "webhook":
            url = self.webhook_url_input.text().strip()
            if not url:
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.webhook_url_required"),
                )
                self.webhook_url_input.setFocus()
                return

        elif handler_type == "google sheets":
            if self.creds_path_input.text().strip() == "":
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.creds_path_required"),
                )
                self.creds_path_input.setFocus()
                return
            if self.spreadsheet_url_input.text().strip() == "":
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.spreadsheet_url_required"),
                )
                self.spreadsheet_url_input.setFocus()
                return
            if self.sheet_id_input.text().strip() == "":
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.sheet_id_required"),
                )
                self.sheet_id_input.setFocus()
                return

            if not os.path.exists(self.creds_path_input.text()):
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.creds_path_invalid"),
                )
                self.spreadsheet_url_input.setFocus()
                return

            id_match = re.search(
                r"(?<=https://docs.google.com/spreadsheets/d/).*(?=/)",
                self.spreadsheet_url_input.text(),
            )

            if id_match is None:
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.spreadsheet_url_invalid"),
                )
                self.spreadsheet_url_input.setFocus()
                return

            sheet_id = self.sheet_id_input.text().strip()

            if not sheet_id:
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.sheet_id_invalid"),
                )
                return

            if not bool(re.search("[a-zA-Z]+[1-9][0-9]*", self.start_cell_input.text())):
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.start_cell_invalid"),
                )
                return

            if self.row_format_input.text().strip() == "":
                QMessageBox.warning(
                    self,
                    t("common.validation_error"),
                    t("output_tab.handler_dialog.row_format_missing"),
                )
                return

        self.accept()

    def get_handler_config(self) -> OutputHandlerConfig:
        """Get handler config from dialog input.

        Returns:
            OutputHandlerConfig with current values.
        """
        handler_type = OutputHandlerType(self.handler_type_input.currentText())
        name = self.name_input.text().strip()

        # Create format settings based on selection
        format_type_str = self.format_input.currentText()
        format_settings: JsonFormatSettings | CsvFormatSettings
        if format_type_str == "csv":
            format_settings = CsvFormatSettings(type=OutputFormat.CSV)
        elif format_type_str == "tsv":
            format_settings = CsvFormatSettings(type=OutputFormat.TSV)
        else:
            format_settings = JsonFormatSettings()

        # Create appropriate handler settings based on type
        handler_settings: (
            ReturnHandlerSettings
            | FileHandlerSettings
            | WebhookHandlerSettings
            | ConsoleHandlerSettings
            | SheetsHandlerSettings
        )
        if handler_type == OutputHandlerType.FILE:
            handler_settings = FileHandlerSettings(path=self.file_path_input.text() or "output")
            if not name:
                name = "File Output"
        elif handler_type == OutputHandlerType.WEBHOOK:
            webhook_auth_type_str = self.webhook_auth_type_input.currentText()
            webhook_auth_type: AuthType | None = (
                None if webhook_auth_type_str == "null" else AuthType(webhook_auth_type_str)
            )
            handler_settings = WebhookHandlerSettings(
                url=self.webhook_url_input.text() or "https://example.com/webhook",
                auth_type=webhook_auth_type,
                token=self.webhook_token_input.text() or None,
                client_auth_header=self.webhook_client_auth_input.text() or None,
            )
            if not name:
                name = "Webhook"
        elif handler_type == OutputHandlerType.CONSOLE:
            handler_settings = ConsoleHandlerSettings()
            if not name:
                name = "Console"
        elif handler_type == OutputHandlerType.SHEETS:
            handler_settings = SheetsHandlerSettings(
                creds_path=self.creds_path_input.text(),
                spreadsheet_url=self.spreadsheet_url_input.text(),
                sheet_id=self.sheet_id_input.text(),
                start_cell=self.start_cell_input.text(),
                row_format=self.row_format_input.text(),
            )
            if not name:
                name = "Append rows (Google Sheets)"
        else:  # RETURN
            handler_settings = ReturnHandlerSettings()
            if not name:
                name = "API Response"

        return OutputHandlerConfig(
            name=name,
            format=format_settings,
            handler=handler_settings,
        )

    def browse_credentials(self) -> None:
        """Open file dialog for credentials path."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            t("output_tab.handler_dialog.select_creds"),
            "",
            "JSON (*.json);;All Files (*)",
        )
        if filepath:
            self.creds_path_input.setText(filepath)


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
