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
    DiscordHandlerSettings,
    FileHandlerSettings,
    ImageHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    ReturnHandlerSettings,
    SheetsHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.core.settings.sections.output.discord_handler import (
    is_discord_webhook_url,
)
from foxhole_stockpiles.core.settings.sections.output.sheets_handler import SPREADSHEET_URL_PATTERN
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType
from foxhole_stockpiles.gui.widgets.config_tabs.discord_output_group import DiscordOutputGroup
from foxhole_stockpiles.gui.widgets.config_tabs.image_output_group import ImageOutputGroup
from foxhole_stockpiles.gui.widgets.config_tabs.stockpile_selection_group import (
    StockpileSelectionGroup,
)
from foxhole_stockpiles.gui.widgets.placeholder_help_button import PlaceholderHelpButton
from foxhole_stockpiles.i18n import on_language_changed, t

_DEFAULT_NAMES = {
    OutputHandlerType.FILE: "File Output",
    OutputHandlerType.WEBHOOK: "Webhook",
    OutputHandlerType.CONSOLE: "Console",
    OutputHandlerType.SHEETS: "Append rows (Google Sheets)",
    OutputHandlerType.RETURN: "API Response",
    OutputHandlerType.IMAGE: "Image",
    OutputHandlerType.DISCORD: "Discord",
}


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

        layout.addWidget(self._build_basic_group())
        layout.addWidget(self._build_file_group())
        layout.addWidget(self._build_webhook_group())
        layout.addWidget(self._build_sheets_group())
        self.image_group = ImageOutputGroup()
        layout.addWidget(self.image_group)
        self.discord_group = DiscordOutputGroup()
        layout.addWidget(self.discord_group)
        self.selection_group = StockpileSelectionGroup()
        layout.addWidget(self.selection_group)

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
        on_language_changed(self._on_language_changed)

    def _build_basic_group(self) -> QGroupBox:
        """Build the name, handler type and format fields.

        Returns:
            QGroupBox: The group.
        """
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

        return self.basic_group

    def _build_file_group(self) -> QGroupBox:
        """Build the fields of the file handler.

        Returns:
            QGroupBox: The group.
        """
        self.file_group = QGroupBox()
        file_layout = QFormLayout()
        self.file_group.setLayout(file_layout)

        self.file_path_label = QLabel()
        file_path_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_browse_btn = QPushButton()
        self.file_browse_btn.clicked.connect(self._browse_file)
        self.file_path_help = PlaceholderHelpButton()
        file_path_layout.addWidget(self.file_path_input)
        file_path_layout.addWidget(self.file_path_help)
        file_path_layout.addWidget(self.file_browse_btn)
        file_layout.addRow(self.file_path_label, file_path_layout)

        return self.file_group

    def _build_webhook_group(self) -> QGroupBox:
        """Build the fields of the webhook handler.

        Returns:
            QGroupBox: The group.
        """
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

        return self.webhook_group

    def _build_sheets_group(self) -> QGroupBox:
        """Build the fields of the Google Sheets handler.

        Returns:
            QGroupBox: The group.
        """
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

        return self.sheets_group

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
        self.file_path_help.retranslate()

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

        self.image_group.retranslate()
        self.discord_group.retranslate()
        self.selection_group.retranslate()

    def _on_handler_type_changed(self) -> None:
        """Handle handler type change to show/hide relevant sections."""
        handler_type = OutputHandlerType(self.handler_type_input.currentText())
        self.file_group.setVisible(handler_type == OutputHandlerType.FILE)
        self.webhook_group.setVisible(handler_type == OutputHandlerType.WEBHOOK)
        self.sheets_group.setVisible(handler_type == OutputHandlerType.SHEETS)
        self.image_group.setVisible(handler_type == OutputHandlerType.IMAGE)
        self.discord_group.setVisible(handler_type == OutputHandlerType.DISCORD)
        # Show format selection only for file handler (webhook/return are JSON-only)
        show_format = handler_type == OutputHandlerType.FILE
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
        self.format_input.setCurrentText(str(handler_config.format.type))
        self.selection_group.load(
            public_stockpiles=handler_config.public_stockpiles,
            grouping=handler_config.grouping,
        )

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
        elif isinstance(handler, ImageHandlerSettings):
            self.image_group.load(handler)
        elif isinstance(handler, DiscordHandlerSettings):
            self.discord_group.load(handler)

        self._on_handler_type_changed()
        self._on_webhook_auth_changed()

    def _required_fields(self) -> dict[OutputHandlerType, tuple[tuple[QLineEdit, str], ...]]:
        """Return the fields each handler type requires, in validation order.

        Returns:
            dict[OutputHandlerType, tuple[tuple[QLineEdit, str], ...]]: For each
                handler type, its (field, missing-value message key) pairs.
        """
        return {
            OutputHandlerType.FILE: (
                (self.file_path_input, "output_tab.handler_dialog.file_path_required"),
            ),
            OutputHandlerType.WEBHOOK: (
                (self.webhook_url_input, "output_tab.handler_dialog.webhook_url_required"),
            ),
            OutputHandlerType.SHEETS: (
                (self.creds_path_input, "output_tab.handler_dialog.creds_path_required"),
                (self.spreadsheet_url_input, "output_tab.handler_dialog.spreadsheet_url_required"),
                (self.sheet_id_input, "output_tab.handler_dialog.sheet_id_required"),
            ),
            OutputHandlerType.IMAGE: (
                (self.image_group.path_input, "output_tab.handler_dialog.image_path_required"),
            ),
            OutputHandlerType.DISCORD: (
                (self.discord_group.url_input, "output_tab.handler_dialog.discord_url_invalid"),
            ),
        }

    def _warn(self, message_key: str, widget: QLineEdit | None = None) -> None:
        """Show a validation warning, optionally focusing a field.

        Args:
            message_key: Translation key for the validation error message.
            widget: Field to focus after showing the warning, if any.
        """
        QMessageBox.warning(self, t("common.validation_error"), t(message_key))
        if widget is not None:
            widget.setFocus()

    def _sheets_values_valid(self) -> bool:
        """Check the format of the Google Sheets values, warning on the first problem.

        Returns:
            bool: True if every value is valid, False if a warning was shown.
        """
        if not os.path.exists(self.creds_path_input.text()):
            self._warn(
                message_key="output_tab.handler_dialog.creds_path_invalid",
                widget=self.creds_path_input,
            )
            return False

        if SPREADSHEET_URL_PATTERN.search(self.spreadsheet_url_input.text().strip()) is None:
            self._warn(
                "output_tab.handler_dialog.spreadsheet_url_invalid", self.spreadsheet_url_input
            )
            return False

        if not bool(re.search("[a-zA-Z]+[1-9][0-9]*", self.start_cell_input.text())):
            self._warn("output_tab.handler_dialog.start_cell_invalid")
            return False

        if self.row_format_input.text().strip() == "":
            self._warn("output_tab.handler_dialog.row_format_missing")
            return False

        return True

    def _validate_and_accept(self) -> None:
        """Validate input and accept dialog if valid."""
        handler_type = OutputHandlerType(self.handler_type_input.currentText())

        for widget, message_key in self._required_fields().get(handler_type, ()):
            if not widget.text().strip():
                self._warn(message_key=message_key, widget=widget)
                return

        if handler_type == OutputHandlerType.SHEETS and not self._sheets_values_valid():
            return

        if handler_type == OutputHandlerType.DISCORD and not is_discord_webhook_url(
            self.discord_group.url_input.text().strip()
        ):
            self._warn(
                message_key="output_tab.handler_dialog.discord_url_invalid",
                widget=self.discord_group.url_input,
            )
            return

        self.accept()

    def get_handler_config(self) -> OutputHandlerConfig:
        """Get handler config from dialog input.

        Returns:
            OutputHandlerConfig with current values.
        """
        handler_type = OutputHandlerType(self.handler_type_input.currentText())
        return OutputHandlerConfig.model_validate(
            {
                "name": self.name_input.text().strip() or _DEFAULT_NAMES[handler_type],
                "format": self._read_format(),
                "handler": self._read_handler_settings(handler_type),
                **self.selection_group.values(),
            }
        )

    def _read_format(self) -> JsonFormatSettings | CsvFormatSettings:
        """Read the selected output format.

        Returns:
            JsonFormatSettings | CsvFormatSettings: The settings of that format.
        """
        match self.format_input.currentText():
            case "csv":
                return CsvFormatSettings(type=OutputFormat.CSV)
            case "tsv":
                return CsvFormatSettings(type=OutputFormat.TSV)
            case _:
                return JsonFormatSettings()

    def _read_handler_settings(
        self, handler_type: OutputHandlerType
    ) -> (
        ReturnHandlerSettings
        | FileHandlerSettings
        | WebhookHandlerSettings
        | ConsoleHandlerSettings
        | SheetsHandlerSettings
        | ImageHandlerSettings
        | DiscordHandlerSettings
    ):
        """Read the fields of a handler type.

        Args:
            handler_type (OutputHandlerType): The selected type.

        Returns:
            ReturnHandlerSettings | FileHandlerSettings | WebhookHandlerSettings
                | ConsoleHandlerSettings | SheetsHandlerSettings | ImageHandlerSettings
                | DiscordHandlerSettings: Its settings.
        """
        match handler_type:
            case OutputHandlerType.FILE:
                return FileHandlerSettings(path=self.file_path_input.text() or "output")
            case OutputHandlerType.WEBHOOK:
                auth_type = self.webhook_auth_type_input.currentText()
                return WebhookHandlerSettings(
                    url=self.webhook_url_input.text() or "https://example.com/webhook",
                    auth_type=None if auth_type == "null" else AuthType(auth_type),
                    token=self.webhook_token_input.text() or None,
                    auth_header=self.webhook_auth_header_input.text() or None,
                )
            case OutputHandlerType.CONSOLE:
                return ConsoleHandlerSettings()
            case OutputHandlerType.SHEETS:
                return SheetsHandlerSettings(
                    creds_path=self.creds_path_input.text(),
                    spreadsheet_url=self.spreadsheet_url_input.text().strip(),
                    sheet_id=self.sheet_id_input.text(),
                    start_cell=self.start_cell_input.text(),
                    row_format=self.row_format_input.text(),
                )
            case OutputHandlerType.IMAGE:
                return self.image_group.read()
            case OutputHandlerType.DISCORD:
                return self.discord_group.read()
            case _:  # RETURN
                return ReturnHandlerSettings()

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
