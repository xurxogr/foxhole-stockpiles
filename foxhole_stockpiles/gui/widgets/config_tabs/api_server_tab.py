"""API Server settings tab."""

import json

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.core.settings.sections.api import APIAuthSettings, APIServerSettings
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.config_level import ConfigLevel
from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t


class APIServerTab(QWidget):
    """Tab for API Server configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the API Server tab.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        # Track widgets that should be hidden at basic level
        self._advanced_widgets: list[QWidget] = []
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Server Settings Group
        self.server_group = QGroupBox()
        server_layout = QFormLayout()
        self.server_group.setLayout(server_layout)

        # Host
        self.host_label = QLabel()
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("127.0.0.1")
        server_layout.addRow(self.host_label, self.host_input)

        # Port
        self.port_label = QLabel()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8000)
        server_layout.addRow(self.port_label, self.port_input)

        # Workers
        self.workers_label = QLabel()
        self.workers_input = QSpinBox()
        self.workers_input.setRange(1, 32)
        self.workers_input.setValue(1)
        server_layout.addRow(self.workers_label, self.workers_input)

        # Max Concurrent Scans
        self.max_concurrent_scans_label = QLabel()
        self.max_concurrent_scans_input = QSpinBox()
        self.max_concurrent_scans_input.setRange(0, 32)
        self.max_concurrent_scans_input.setValue(0)
        self.max_concurrent_scans_input.setSpecialValueText("Disabled")
        server_layout.addRow(self.max_concurrent_scans_label, self.max_concurrent_scans_input)

        # CORS Allow Origins - ADVANCED
        self._cors_label = QLabel()
        self.cors_input = QPlainTextEdit()
        self.cors_input.setPlaceholderText('["*"] or ["http://localhost:3000"]')
        self.cors_input.setMaximumHeight(80)
        server_layout.addRow(self._cors_label, self.cors_input)
        self._advanced_widgets.extend([self._cors_label, self.cors_input])

        # Enable Memory Monitoring
        self.memory_label = QLabel()
        self.memory_monitoring_input = QCheckBox()
        server_layout.addRow(self.memory_label, self.memory_monitoring_input)

        # Auto Trim Memory
        self.trim_label = QLabel()
        self.auto_trim_input = QCheckBox()
        self.auto_trim_input.setChecked(True)
        server_layout.addRow(self.trim_label, self.auto_trim_input)

        layout.addWidget(self.server_group)

        # Authentication Group
        self.auth_group = QGroupBox()
        auth_layout = QVBoxLayout()
        self.auth_group.setLayout(auth_layout)

        # Auth Type Selection with Radio Buttons
        auth_type_layout = QHBoxLayout()

        self.auth_type_button_group = QButtonGroup(self)

        self.no_auth_radio = QRadioButton()
        self.no_auth_radio.setChecked(True)
        self.auth_type_button_group.addButton(self.no_auth_radio, 0)
        auth_type_layout.addWidget(self.no_auth_radio)

        self.basic_auth_radio = QRadioButton()
        self.auth_type_button_group.addButton(self.basic_auth_radio, 1)
        auth_type_layout.addWidget(self.basic_auth_radio)

        self.bearer_auth_radio = QRadioButton()
        self.auth_type_button_group.addButton(self.bearer_auth_radio, 2)
        auth_type_layout.addWidget(self.bearer_auth_radio)

        auth_type_layout.addStretch()
        self.auth_type_button_group.buttonClicked.connect(self._update_auth_visibility)

        auth_layout.addLayout(auth_type_layout)

        # Basic Auth Fields
        self.basic_auth_widget = QWidget()
        basic_layout = QFormLayout(self.basic_auth_widget)
        basic_layout.setContentsMargins(0, 0, 0, 0)

        self.username_label = QLabel()
        self.basic_username_input = QLineEdit()
        self.basic_username_input.setPlaceholderText("Username")
        basic_layout.addRow(self.username_label, self.basic_username_input)

        self.password_label = QLabel()
        self.basic_password_input = QLineEdit()
        self.basic_password_input.setPlaceholderText("Password")
        self.basic_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        basic_layout.addRow(self.password_label, self.basic_password_input)

        auth_layout.addWidget(self.basic_auth_widget)

        # Bearer Token Fields
        self.bearer_auth_widget = QWidget()
        bearer_layout = QFormLayout(self.bearer_auth_widget)
        bearer_layout.setContentsMargins(0, 0, 0, 0)

        self.token_label = QLabel()
        self.bearer_token_input = QLineEdit()
        self.bearer_token_input.setPlaceholderText("Enter bearer token")
        self.bearer_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        bearer_layout.addRow(self.token_label, self.bearer_token_input)

        auth_layout.addWidget(self.bearer_auth_widget)

        layout.addWidget(self.auth_group)
        layout.addStretch()

        # Initially show/hide based on default selection
        self._update_auth_visibility()

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
        # Server Settings Group
        self.server_group.setTitle(t("api_server_tab.server_settings"))

        self.host_label.setText(t("api_server_tab.host"))
        self.host_label.setToolTip(t("api_server_tab.host_tooltip"))

        self.port_label.setText(t("api_server_tab.port"))
        self.port_label.setToolTip(t("api_server_tab.port_tooltip"))

        self.workers_label.setText(t("api_server_tab.workers"))
        self.workers_label.setToolTip(t("api_server_tab.workers_tooltip"))

        self.max_concurrent_scans_label.setText(t("api_server_tab.max_concurrent_scans"))
        self.max_concurrent_scans_label.setToolTip(t("api_server_tab.max_concurrent_scans_tooltip"))

        self._cors_label.setText(t("api_server_tab.cors_origins"))
        self._cors_label.setToolTip(t("api_server_tab.cors_tooltip"))

        self.memory_label.setText(t("api_server_tab.memory_monitoring"))
        self.memory_label.setToolTip(t("api_server_tab.memory_tooltip"))
        self.memory_monitoring_input.setText(t("api_server_tab.memory_monitoring_checkbox"))

        self.trim_label.setText(t("api_server_tab.auto_trim"))
        self.trim_label.setToolTip(t("api_server_tab.auto_trim_tooltip"))
        self.auto_trim_input.setText(t("api_server_tab.auto_trim_checkbox"))

        # Authentication Group
        self.auth_group.setTitle(t("api_server_tab.authentication"))

        self.no_auth_radio.setText(t("api_server_tab.no_auth"))
        self.no_auth_radio.setToolTip(t("api_server_tab.no_auth_tooltip"))

        self.basic_auth_radio.setText(t("api_server_tab.basic_auth"))
        self.basic_auth_radio.setToolTip(t("api_server_tab.basic_auth_tooltip"))

        self.bearer_auth_radio.setText(t("api_server_tab.bearer_auth"))
        self.bearer_auth_radio.setToolTip(t("api_server_tab.bearer_auth_tooltip"))

        self.username_label.setText(t("api_server_tab.username"))
        self.password_label.setText(t("api_server_tab.password"))

        self.token_label.setText(t("api_server_tab.token"))
        self.token_label.setToolTip(t("api_server_tab.token_tooltip"))

    def _update_auth_visibility(self) -> None:
        """Update visibility of auth fields based on selected radio button."""
        self.basic_auth_widget.setVisible(self.basic_auth_radio.isChecked())
        self.bearer_auth_widget.setVisible(self.bearer_auth_radio.isChecked())

    def set_values(
        self, server_settings: APIServerSettings, auth_settings: APIAuthSettings | None = None
    ) -> None:
        """Set widget values from settings.

        Args:
            server_settings (APIServerSettings): APIServerSettings instance to load values from.
            auth_settings (APIAuthSettings | None): APIAuthSettings instance to load values from.
        """
        # Server settings
        self.host_input.setText(server_settings.host)
        self.port_input.setValue(server_settings.port)
        self.workers_input.setValue(server_settings.workers)
        self.max_concurrent_scans_input.setValue(server_settings.max_concurrent_scans)

        # Convert list to JSON string for display
        cors_text = json.dumps(server_settings.cors_allow_origins, indent=2)
        self.cors_input.setPlainText(cors_text)

        self.memory_monitoring_input.setChecked(server_settings.enable_memory_monitoring)
        self.auto_trim_input.setChecked(server_settings.auto_trim_memory)

        # Auth settings
        if auth_settings:
            auth_type = auth_settings.auth_type or "null"
            if auth_type == "basic":
                self.basic_auth_radio.setChecked(True)
            elif auth_type == "bearer":
                self.bearer_auth_radio.setChecked(True)
            else:
                self.no_auth_radio.setChecked(True)

            # Parse and set credentials based on type
            if auth_settings.auth_token:
                if auth_type == "basic":
                    # Basic auth token format: "username:password"
                    if ":" in auth_settings.auth_token:
                        username, password = auth_settings.auth_token.split(":", 1)
                        self.basic_username_input.setText(username)
                        self.basic_password_input.setText(password)
                    else:
                        self.basic_username_input.setText(auth_settings.auth_token)
                elif auth_type == "bearer":
                    self.bearer_token_input.setText(auth_settings.auth_token)

            self._update_auth_visibility()

    def get_server_values(self) -> APIServerSettings:
        """Get current server values from widgets.

        Returns:
            APIServerSettings: APIServerSettings instance with current values from widgets
        """
        # Parse CORS origins from text
        try:
            cors_origins = json.loads(self.cors_input.toPlainText())
        except json.JSONDecodeError:
            cors_origins = ["*"]

        return APIServerSettings(
            host=self.host_input.text(),
            port=self.port_input.value(),
            workers=self.workers_input.value(),
            max_concurrent_scans=self.max_concurrent_scans_input.value(),
            cors_allow_origins=cors_origins,
            log_level="info",  # Use default, configured in Logging tab
            reload=False,  # Always False for GUI users (development-only option)
            enable_memory_monitoring=self.memory_monitoring_input.isChecked(),
            auto_trim_memory=self.auto_trim_input.isChecked(),
        )

    def set_config_level(self, level: ConfigLevel) -> None:
        """Show or hide fields based on the configuration level.

        Args:
            level (ConfigLevel): The configuration level to set.
        """
        # Advanced widgets are visible at advanced and developer levels
        for widget in self._advanced_widgets:
            widget.setVisible(level.is_at_least(ConfigLevel.ADVANCED))

    def get_auth_values(self) -> APIAuthSettings:
        """Get current auth values from widgets.

        Returns:
            APIAuthSettings: APIAuthSettings instance with current values from widgets
        """
        # Determine auth type from radio buttons
        if self.basic_auth_radio.isChecked():
            auth_type = "basic"
        elif self.bearer_auth_radio.isChecked():
            auth_type = "bearer"
        else:
            auth_type = "null"

        # Build auth token based on type
        auth_token = None
        if auth_type == "basic":
            username = self.basic_username_input.text().strip()
            password = self.basic_password_input.text().strip()
            if username or password:
                auth_token = f"{username}:{password}"
        elif auth_type == "bearer":
            token = self.bearer_token_input.text().strip()
            if token:
                auth_token = token

        # If token is None but auth_type is set, reset auth_type to None
        if auth_token is None:
            auth_type = "null"

        return APIAuthSettings(
            auth_type=None if auth_type == "null" else AuthType(auth_type),
            auth_token=auth_token,
        )
