"""Dialog for adding or editing an output handler."""

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
        self.handler_type_input.addItems([t.value for t in OutputHandlerType])
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
        self.webhook_auth_type_input.addItems(["null", "basic", "bearer", "header"])
        self.webhook_auth_type_input.currentTextChanged.connect(self._on_webhook_auth_changed)
        webhook_layout.addRow(self.auth_type_label, self.webhook_auth_type_input)

        self.auth_header_label = QLabel()
        self.webhook_auth_header_input = QLineEdit()
        webhook_layout.addRow(self.auth_header_label, self.webhook_auth_header_input)

        self.auth_token_label = QLabel()
        self.webhook_token_input = QLineEdit()
        self.webhook_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        webhook_layout.addRow(self.auth_token_label, self.webhook_token_input)

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
        self.auth_header_label.setText(t("output_tab.handler_dialog.auth_header"))
        self.auth_header_label.setToolTip(t("output_tab.handler_dialog.auth_header_tooltip"))
        self.webhook_auth_header_input.setPlaceholderText(
            t("output_tab.handler_dialog.auth_header_placeholder")
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

        # Show token fields for basic/bearer/header, hide for null
        show_token = auth_type in ("basic", "bearer", "header")
        self.auth_token_label.setVisible(show_token)
        self.webhook_token_input.setVisible(show_token)

        # Show the custom header-name field only for header auth
        show_auth_header = auth_type == "header"
        self.auth_header_label.setVisible(show_auth_header)
        self.webhook_auth_header_input.setVisible(show_auth_header)

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
            self.webhook_auth_header_input.setText(handler.auth_header or "")
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
                auth_header=self.webhook_auth_header_input.text() or None,
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
