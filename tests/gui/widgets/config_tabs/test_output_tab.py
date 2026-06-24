"""Tests for OutputTab."""

from typing import Any
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox

from foxhole_stockpiles.core.settings.sections.output import (
    CsvFormatSettings,
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    SheetsHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.output_handler_type import OutputHandlerType
from foxhole_stockpiles.gui.widgets.config_tabs.output_tab import (
    OutputHandlerDialog,
    OutputTab,
)
from foxhole_stockpiles.i18n import t


@pytest.fixture
def output_tab(qtbot: Any) -> OutputTab:
    """Create an OutputTab instance.

    Args:
        qtbot: PyQt test fixture

    Returns:
        OutputTab: Tab instance
    """
    tab = OutputTab()
    qtbot.addWidget(tab)
    return tab


@pytest.fixture
def sample_file_handler() -> OutputHandlerConfig:
    """Create a sample file handler config.

    Returns:
        OutputHandlerConfig: Sample file handler
    """
    return OutputHandlerConfig(
        name="File Backup",
        format=JsonFormatSettings(),
        handler=FileHandlerSettings(path="/output/data.json"),
    )


@pytest.fixture
def sample_webhook_handler() -> OutputHandlerConfig:
    """Create a sample webhook handler config.

    Returns:
        OutputHandlerConfig: Sample webhook handler
    """
    return OutputHandlerConfig(
        name="API Webhook",
        format=JsonFormatSettings(),
        handler=WebhookHandlerSettings(
            url="https://example.com/webhook",
            auth_type=AuthType.BEARER,
            token="secret-token",
        ),
    )


class TestOutputTabInitialization:
    """Tests for OutputTab initialization."""

    def test_initialization(self, output_tab: OutputTab) -> None:
        """Test OutputTab initialization.

        Args:
            output_tab: OutputTab instance
        """
        assert output_tab.handlers_list is not None
        assert output_tab.add_button is not None
        assert output_tab.edit_button is not None
        assert output_tab.remove_button is not None

    def test_initial_state(self, output_tab: OutputTab) -> None:
        """Test initial state is empty with no handlers.

        Args:
            output_tab: OutputTab instance
        """
        assert output_tab.handlers_list.count() == 0
        assert len(output_tab._handlers) == 0

    def test_edit_remove_buttons_disabled_initially(self, output_tab: OutputTab) -> None:
        """Test edit and remove buttons are disabled when no selection.

        Args:
            output_tab: OutputTab instance
        """
        assert not output_tab.edit_button.isEnabled()
        assert not output_tab.remove_button.isEnabled()


class TestOutputTabSetValues:
    """Tests for OutputTab set_values method."""

    def test_set_values_with_handler(
        self, output_tab: OutputTab, sample_file_handler: OutputHandlerConfig
    ) -> None:
        """Test setting values with a handler.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        settings = OutputSettings(handlers=[sample_file_handler])

        output_tab.set_values(settings)

        assert output_tab.handlers_list.count() == 1
        assert len(output_tab._handlers) == 1

    def test_set_values_empty(self, output_tab: OutputTab) -> None:
        """Test setting empty values.

        Args:
            output_tab: OutputTab instance
        """
        settings = OutputSettings(handlers=[])

        output_tab.set_values(settings)

        assert output_tab.handlers_list.count() == 0
        assert len(output_tab._handlers) == 0

    def test_set_values_multiple_handlers(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
        sample_webhook_handler: OutputHandlerConfig,
    ) -> None:
        """Test setting values with multiple handlers.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
            sample_webhook_handler: Sample webhook handler
        """
        settings = OutputSettings(handlers=[sample_file_handler, sample_webhook_handler])

        output_tab.set_values(settings)

        assert output_tab.handlers_list.count() == 2
        assert len(output_tab._handlers) == 2

    def test_set_values_list_display_file(
        self, output_tab: OutputTab, sample_file_handler: OutputHandlerConfig
    ) -> None:
        """Test list display for file handler shows path.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        settings = OutputSettings(handlers=[sample_file_handler])

        output_tab.set_values(settings)

        item = output_tab.handlers_list.item(0)
        assert item is not None
        assert "/output/data.json" in item.text()

    def test_set_values_list_display_webhook(
        self, output_tab: OutputTab, sample_webhook_handler: OutputHandlerConfig
    ) -> None:
        """Test list display for webhook handler shows URL.

        Args:
            output_tab: OutputTab instance
            sample_webhook_handler: Sample webhook handler
        """
        settings = OutputSettings(handlers=[sample_webhook_handler])

        output_tab.set_values(settings)

        item = output_tab.handlers_list.item(0)
        assert item is not None
        assert "example.com" in item.text()


class TestOutputTabGetValues:
    """Tests for OutputTab get_values method."""

    def test_get_values_default(self, output_tab: OutputTab) -> None:
        """Test getting default values.

        Args:
            output_tab: OutputTab instance
        """
        settings = output_tab.get_values()

        assert len(settings.handlers) == 0

    def test_get_values_with_handlers(
        self, output_tab: OutputTab, sample_file_handler: OutputHandlerConfig
    ) -> None:
        """Test getting values with handlers.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        output_tab._handlers = [sample_file_handler]
        output_tab._update_list()

        settings = output_tab.get_values()

        assert len(settings.handlers) == 1
        assert settings.handlers[0].name == "File Backup"
        assert settings.handlers[0].handler.type == OutputHandlerType.FILE

    def test_roundtrip(
        self, output_tab: OutputTab, sample_file_handler: OutputHandlerConfig
    ) -> None:
        """Test that set_values and get_values preserve data.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        original = OutputSettings(handlers=[sample_file_handler])

        output_tab.set_values(original)
        result = output_tab.get_values()

        assert len(result.handlers) == len(original.handlers)
        assert result.handlers[0].name == original.handlers[0].name
        assert result.handlers[0].handler.type == original.handlers[0].handler.type
        result_handler = result.handlers[0].handler
        original_handler = original.handlers[0].handler
        assert isinstance(result_handler, FileHandlerSettings)
        assert isinstance(original_handler, FileHandlerSettings)
        assert result_handler.path == original_handler.path


class TestOutputTabButtons:
    """Tests for add/edit/remove button handlers."""

    def test_on_add_clicked_accepted(
        self,
        qtbot: Any,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
    ) -> None:
        """Test adding a handler when dialog is accepted.

        Args:
            qtbot: PyQt test fixture
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.OutputHandlerDialog"
        ) as mock_dialog_class:
            mock_dialog = mock_dialog_class.return_value
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_handler_config.return_value = sample_file_handler

            output_tab._on_add_clicked()

            assert len(output_tab._handlers) == 1
            assert output_tab._handlers[0] == sample_file_handler
            assert output_tab.handlers_list.count() == 1
            assert output_tab.handlers_list.currentRow() == 0

    def test_on_add_clicked_cancelled(self, output_tab: OutputTab) -> None:
        """Test adding a handler when dialog is cancelled.

        Args:
            output_tab: OutputTab instance
        """
        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.OutputHandlerDialog"
        ) as mock_dialog_class:
            mock_dialog = mock_dialog_class.return_value
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

            output_tab._on_add_clicked()

            assert len(output_tab._handlers) == 0
            assert output_tab.handlers_list.count() == 0

    def test_on_edit_clicked_no_selection(self, output_tab: OutputTab) -> None:
        """Test edit click with no selection does nothing.

        Args:
            output_tab: OutputTab instance
        """
        # No items, no selection
        output_tab._on_edit_clicked()
        # Should not raise, just return early
        assert len(output_tab._handlers) == 0

    def test_on_edit_clicked_accepted(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
    ) -> None:
        """Test editing a handler when dialog is accepted.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        # Add initial handler
        output_tab._handlers = [sample_file_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(0)

        updated_handler = OutputHandlerConfig(
            name="Updated Name",
            format=JsonFormatSettings(),
            handler=FileHandlerSettings(path="/updated/path.json"),
        )

        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.OutputHandlerDialog"
        ) as mock_dialog_class:
            mock_dialog = mock_dialog_class.return_value
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_handler_config.return_value = updated_handler

            output_tab._on_edit_clicked()

            assert len(output_tab._handlers) == 1
            assert output_tab._handlers[0].name == "Updated Name"
            assert output_tab.handlers_list.currentRow() == 0

    def test_on_remove_clicked_no_selection(self, output_tab: OutputTab) -> None:
        """Test remove click with no selection does nothing.

        Args:
            output_tab: OutputTab instance
        """
        # No items, no selection
        output_tab._on_remove_clicked()
        # Should not raise, just return early
        assert len(output_tab._handlers) == 0

    def test_on_remove_clicked_confirmed(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
    ) -> None:
        """Test removing a handler when user confirms.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        output_tab._handlers = [sample_file_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(0)

        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            output_tab._on_remove_clicked()

            assert len(output_tab._handlers) == 0
            assert output_tab.handlers_list.count() == 0

    def test_on_remove_clicked_cancelled(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
    ) -> None:
        """Test removing a handler when user cancels.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        output_tab._handlers = [sample_file_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(0)

        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            output_tab._on_remove_clicked()

            # Handler should still be there
            assert len(output_tab._handlers) == 1
            assert output_tab.handlers_list.count() == 1

    def test_on_move_up_clicked(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
        sample_webhook_handler: OutputHandlerConfig,
    ) -> None:
        """Test moving a handler up in the list.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
            sample_webhook_handler: Sample webhook handler
        """
        output_tab._handlers = [sample_file_handler, sample_webhook_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(1)  # Select webhook (second)

        output_tab._on_move_up_clicked()

        # Webhook should now be first
        assert output_tab._handlers[0].name == "API Webhook"
        assert output_tab._handlers[1].name == "File Backup"
        assert output_tab.handlers_list.currentRow() == 0

    def test_on_move_up_clicked_at_top(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
    ) -> None:
        """Test move up does nothing when at top of list.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        output_tab._handlers = [sample_file_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(0)

        output_tab._on_move_up_clicked()

        # Nothing should change
        assert len(output_tab._handlers) == 1
        assert output_tab._handlers[0].name == "File Backup"

    def test_on_move_down_clicked(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
        sample_webhook_handler: OutputHandlerConfig,
    ) -> None:
        """Test moving a handler down in the list.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
            sample_webhook_handler: Sample webhook handler
        """
        output_tab._handlers = [sample_file_handler, sample_webhook_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(0)  # Select file (first)

        output_tab._on_move_down_clicked()

        # File should now be second
        assert output_tab._handlers[0].name == "API Webhook"
        assert output_tab._handlers[1].name == "File Backup"
        assert output_tab.handlers_list.currentRow() == 1

    def test_on_move_down_clicked_at_bottom(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
    ) -> None:
        """Test move down does nothing when at bottom of list.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
        """
        output_tab._handlers = [sample_file_handler]
        output_tab._update_list()
        output_tab.handlers_list.setCurrentRow(0)

        output_tab._on_move_down_clicked()

        # Nothing should change
        assert len(output_tab._handlers) == 1
        assert output_tab._handlers[0].name == "File Backup"

    def test_move_buttons_state(
        self,
        output_tab: OutputTab,
        sample_file_handler: OutputHandlerConfig,
        sample_webhook_handler: OutputHandlerConfig,
    ) -> None:
        """Test move buttons are enabled/disabled correctly.

        Args:
            output_tab: OutputTab instance
            sample_file_handler: Sample file handler
            sample_webhook_handler: Sample webhook handler
        """
        output_tab._handlers = [sample_file_handler, sample_webhook_handler]
        output_tab._update_list()

        # Select first item - up disabled, down enabled
        output_tab.handlers_list.setCurrentRow(0)
        assert output_tab.move_up_button.isEnabled() is False
        assert output_tab.move_down_button.isEnabled() is True

        # Select last item - up enabled, down disabled
        output_tab.handlers_list.setCurrentRow(1)
        assert output_tab.move_up_button.isEnabled() is True
        assert output_tab.move_down_button.isEnabled() is False


class TestOutputHandlerDialog:
    """Tests for OutputHandlerDialog."""

    def test_dialog_initialization_new(self, qtbot: Any) -> None:
        """Test dialog initialization for new handler.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == t("output_tab.handler_dialog.title_add")
        assert dialog.name_input.text() == ""
        assert dialog.handler_type_input.currentText() == "return"

    def test_dialog_initialization_edit_file(
        self, qtbot: Any, sample_file_handler: OutputHandlerConfig
    ) -> None:
        """Test dialog initialization for editing file handler.

        Args:
            qtbot: PyQt test fixture
            sample_file_handler: Sample file handler
        """
        dialog = OutputHandlerDialog(handler_config=sample_file_handler)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == t("output_tab.handler_dialog.title_edit")
        assert dialog.name_input.text() == "File Backup"
        assert dialog.handler_type_input.currentText() == "file"
        assert dialog.file_path_input.text() == "/output/data.json"

    def test_dialog_initialization_edit_webhook(
        self, qtbot: Any, sample_webhook_handler: OutputHandlerConfig
    ) -> None:
        """Test dialog initialization for editing webhook handler.

        Args:
            qtbot: PyQt test fixture
            sample_webhook_handler: Sample webhook handler
        """
        dialog = OutputHandlerDialog(handler_config=sample_webhook_handler)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == t("output_tab.handler_dialog.title_edit")
        assert dialog.name_input.text() == "API Webhook"
        assert dialog.handler_type_input.currentText() == "webhook"
        assert dialog.webhook_url_input.text() == "https://example.com/webhook"
        assert dialog.webhook_auth_type_input.currentText() == "bearer"
        assert dialog.webhook_token_input.text() == "secret-token"

    def test_dialog_handler_type_shows_file_group(self, qtbot: Any) -> None:
        """Test file handler type shows file group.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.show()

        dialog.handler_type_input.setCurrentText("file")
        dialog._on_handler_type_changed()

        assert dialog.file_group.isVisible()
        assert not dialog.webhook_group.isVisible()

    def test_dialog_handler_type_shows_webhook_group(self, qtbot: Any) -> None:
        """Test webhook handler type shows webhook group.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.show()

        dialog.handler_type_input.setCurrentText("webhook")
        dialog._on_handler_type_changed()

        assert not dialog.file_group.isVisible()
        assert dialog.webhook_group.isVisible()

    def test_dialog_handler_type_return_hides_both(self, qtbot: Any) -> None:
        """Test return handler type hides both groups.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("return")
        dialog._on_handler_type_changed()

        assert not dialog.file_group.isVisible()
        assert not dialog.webhook_group.isVisible()

    def test_dialog_webhook_auth_bearer_shows_token(self, qtbot: Any) -> None:
        """Test bearer auth type shows token field.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.webhook_group.show()

        dialog.webhook_auth_type_input.setCurrentText("bearer")
        dialog._on_webhook_auth_changed()

        assert dialog.auth_token_label.isVisible()
        assert dialog.webhook_token_input.isVisible()
        assert not dialog.client_auth_label.isVisible()
        assert not dialog.webhook_client_auth_input.isVisible()

    def test_dialog_webhook_auth_forward_shows_client_auth(self, qtbot: Any) -> None:
        """Test forward auth type shows client auth field.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.webhook_group.show()

        dialog.webhook_auth_type_input.setCurrentText("forward")
        dialog._on_webhook_auth_changed()

        assert not dialog.auth_token_label.isVisible()
        assert not dialog.webhook_token_input.isVisible()
        assert dialog.client_auth_label.isVisible()
        assert dialog.webhook_client_auth_input.isVisible()

    def test_dialog_webhook_auth_null_hides_fields(self, qtbot: Any) -> None:
        """Test null auth type hides token and client auth fields.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.webhook_auth_type_input.setCurrentText("null")
        dialog._on_webhook_auth_changed()

        assert not dialog.auth_token_label.isVisible()
        assert not dialog.webhook_token_input.isVisible()
        assert not dialog.client_auth_label.isVisible()
        assert not dialog.webhook_client_auth_input.isVisible()

    def test_dialog_get_handler_config_return(self, qtbot: Any) -> None:
        """Test getting return handler config from dialog.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("return")
        dialog.name_input.setText("")  # Test default name

        config = dialog.get_handler_config()

        assert config.name == "API Response"
        assert config.handler.type == OutputHandlerType.RETURN

    def test_dialog_get_handler_config_file(self, qtbot: Any) -> None:
        """Test getting file handler config from dialog.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("file")
        dialog.name_input.setText("My File Handler")
        dialog.file_path_input.setText("/test/output.json")

        config = dialog.get_handler_config()

        assert config.name == "My File Handler"
        assert config.handler.type == OutputHandlerType.FILE
        assert isinstance(config.handler, FileHandlerSettings)
        assert config.handler.path == "/test/output.json"

    def test_dialog_get_handler_config_webhook(self, qtbot: Any) -> None:
        """Test getting webhook handler config from dialog.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("webhook")
        dialog.name_input.setText("My Webhook")
        dialog.webhook_url_input.setText("https://test.com/webhook")
        dialog.webhook_auth_type_input.setCurrentText("bearer")
        dialog.webhook_token_input.setText("my-token")

        config = dialog.get_handler_config()

        assert config.name == "My Webhook"
        assert config.handler.type == OutputHandlerType.WEBHOOK
        assert isinstance(config.handler, WebhookHandlerSettings)
        assert config.handler.url == "https://test.com/webhook"
        assert config.handler.auth_type == AuthType.BEARER
        assert config.handler.token == "my-token"

    def test_dialog_get_handler_config_console(self, qtbot: Any) -> None:
        """Test getting console handler config from dialog.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("console")
        dialog.name_input.setText("")  # Test default name

        config = dialog.get_handler_config()

        assert config.name == "Console"
        assert config.handler.type == OutputHandlerType.CONSOLE

    def test_dialog_validation_file_empty_path(self, qtbot: Any) -> None:
        """Test validation fails for empty file path.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("file")
        dialog.file_path_input.setText("")

        with (
            patch("foxhole_stockpiles.gui.widgets.config_tabs.output_tab.QMessageBox.warning"),
            patch.object(dialog, "accept") as mock_accept,
        ):
            dialog._validate_and_accept()
            mock_accept.assert_not_called()

    def test_dialog_validation_webhook_empty_url(self, qtbot: Any) -> None:
        """Test validation fails for empty webhook URL.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("webhook")
        dialog.webhook_url_input.setText("")

        with (
            patch("foxhole_stockpiles.gui.widgets.config_tabs.output_tab.QMessageBox.warning"),
            patch.object(dialog, "accept") as mock_accept,
        ):
            dialog._validate_and_accept()
            mock_accept.assert_not_called()

    def test_dialog_validation_success_return(self, qtbot: Any) -> None:
        """Test validation succeeds for return handler.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("return")

        with patch.object(dialog, "accept") as mock_accept:
            dialog._validate_and_accept()
            mock_accept.assert_called_once()

    def test_dialog_validation_success_file(self, qtbot: Any) -> None:
        """Test validation succeeds for file handler with path.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("file")
        dialog.file_path_input.setText("/valid/path.json")

        with patch.object(dialog, "accept") as mock_accept:
            dialog._validate_and_accept()
            mock_accept.assert_called_once()

    def test_dialog_validation_success_webhook(self, qtbot: Any) -> None:
        """Test validation succeeds for webhook handler with URL.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        dialog.handler_type_input.setCurrentText("webhook")
        dialog.webhook_url_input.setText("https://example.com/webhook")

        with patch.object(dialog, "accept") as mock_accept:
            dialog._validate_and_accept()
            mock_accept.assert_called_once()

    def test_dialog_browse_file(self, qtbot: Any) -> None:
        """Test browse file button.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        test_path = "/path/to/output.json"

        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = (test_path, "JSON Files (*.json)")

            dialog._browse_file()

            assert dialog.file_path_input.text() == test_path

    def test_dialog_webhook_token_password_echo_mode(self, qtbot: Any) -> None:
        """Test webhook token uses password echo mode.

        Args:
            qtbot: PyQt test fixture
        """
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)

        assert dialog.webhook_token_input.echoMode() == QLineEdit.EchoMode.Password


def _sheets_dialog(qtbot: Any, tmp_path: Any) -> OutputHandlerDialog:
    """Build a Google Sheets dialog pre-filled with valid values."""
    dialog = OutputHandlerDialog()
    qtbot.addWidget(dialog)
    dialog.handler_type_input.setCurrentText("google sheets")
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    dialog.creds_path_input.setText(str(creds))
    dialog.spreadsheet_url_input.setText("https://docs.google.com/spreadsheets/d/ABC123XYZ/edit")
    dialog.sheet_id_input.setText("0")
    dialog.start_cell_input.setText("A1")
    dialog.row_format_input.setText("{code},{quantity}")
    return dialog


class TestOutputHandlerDialogSheets:
    """Google Sheets handler load/validate/build coverage."""

    def test_load_handler_sheets(self, qtbot: Any) -> None:
        """Loading a sheets config populates the sheets fields."""
        config = OutputHandlerConfig(
            name="Sheets",
            format=JsonFormatSettings(),
            handler=SheetsHandlerSettings(
                creds_path="/creds.json",
                spreadsheet_url="https://docs.google.com/spreadsheets/d/ID/edit",
                sheet_id="0",
                start_cell="A1",
                row_format="{code}",
            ),
        )
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.load_handler(config)
        assert dialog.creds_path_input.text() == "/creds.json"
        assert dialog.sheet_id_input.text() == "0"

    def test_valid_sheets_accepts(self, qtbot: Any, tmp_path: Any) -> None:
        """A fully-valid sheets config accepts the dialog."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        with patch.object(OutputHandlerDialog, "accept") as accept:
            dialog._validate_and_accept()
        accept.assert_called_once()

    def test_missing_creds_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """An empty credentials path is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.creds_path_input.setText("")
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_missing_spreadsheet_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """An empty spreadsheet URL is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.spreadsheet_url_input.setText("")
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_missing_sheet_id_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """An empty sheet id is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.sheet_id_input.setText("")
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_creds_not_existing_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """A credentials path that does not exist is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.creds_path_input.setText(str(tmp_path / "missing.json"))
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_invalid_spreadsheet_url_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """A malformed spreadsheet URL is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.spreadsheet_url_input.setText("https://example.com/not-a-sheet")
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_invalid_start_cell_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """A start cell without a row number is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.start_cell_input.setText("ABC")
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_empty_row_format_warns(self, qtbot: Any, tmp_path: Any) -> None:
        """An empty row format is rejected."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        dialog.row_format_input.setText("")
        with patch.object(QMessageBox, "warning") as warn:
            dialog._validate_and_accept()
        warn.assert_called_once()

    def test_get_handler_config_sheets(self, qtbot: Any, tmp_path: Any) -> None:
        """Building a sheets config returns SheetsHandlerSettings."""
        dialog = _sheets_dialog(qtbot, tmp_path)
        config = dialog.get_handler_config()
        assert isinstance(config.handler, SheetsHandlerSettings)
        assert config.handler.sheet_id == "0"
        assert config.name == "Append rows (Google Sheets)"

    def test_browse_credentials(self, qtbot: Any) -> None:
        """browse_credentials sets the chosen file into the creds input."""
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        with patch(
            "foxhole_stockpiles.gui.widgets.config_tabs.output_tab.QFileDialog.getOpenFileName",
            return_value=("/picked/creds.json", ""),
        ):
            dialog.browse_credentials()
        assert dialog.creds_path_input.text() == "/picked/creds.json"


class TestOutputHandlerDialogFormats:
    """Format selection coverage."""

    def test_csv_format(self, qtbot: Any) -> None:
        """Selecting csv builds a CSV format settings object."""
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.handler_type_input.setCurrentText("file")
        dialog.format_input.setCurrentText("csv")
        config = dialog.get_handler_config()
        assert isinstance(config.format, CsvFormatSettings)
        assert config.format.type == OutputFormat.CSV

    def test_tsv_format(self, qtbot: Any) -> None:
        """Selecting tsv builds a TSV format settings object."""
        dialog = OutputHandlerDialog()
        qtbot.addWidget(dialog)
        dialog.handler_type_input.setCurrentText("file")
        dialog.format_input.setCurrentText("tsv")
        config = dialog.get_handler_config()
        assert isinstance(config.format, CsvFormatSettings)
        assert config.format.type == OutputFormat.TSV
