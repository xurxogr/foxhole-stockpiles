"""The fields of the handler that posts stockpiles to Discord."""

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QLineEdit

from foxhole_stockpiles.core.settings.sections.output.discord_handler import (
    DiscordHandlerSettings,
)
from foxhole_stockpiles.gui.widgets.config_tabs.image_appearance_fields import (
    ImageAppearanceFields,
)
from foxhole_stockpiles.i18n import t

_MAX_USERNAME_CHARS = 80


class DiscordOutputGroup(QGroupBox):
    """Which webhook to post to, and how to draw the images."""

    def __init__(self) -> None:
        """Create the fields."""
        super().__init__()
        form = QFormLayout()
        self.setLayout(form)

        self.url_label = QLabel()
        self.url_input = QLineEdit()
        form.addRow(self.url_label, self.url_input)

        self.username_label = QLabel()
        self.username_input = QLineEdit()
        self.username_input.setMaxLength(_MAX_USERNAME_CHARS)
        form.addRow(self.username_label, self.username_input)

        self.avatar_url_label = QLabel()
        self.avatar_url_input = QLineEdit()
        form.addRow(self.avatar_url_label, self.avatar_url_input)

        self.message_label = QLabel()
        self.message_input = QLineEdit()
        form.addRow(self.message_label, self.message_input)

        self.appearance = ImageAppearanceFields(form)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setTitle(t("output_tab.handler_dialog.discord_settings"))
        self.url_label.setText(t("output_tab.handler_dialog.discord_url"))
        self.url_label.setToolTip(t("output_tab.handler_dialog.discord_url_tooltip"))
        self.url_input.setPlaceholderText("https://discord.com/api/webhooks/...")
        self.username_label.setText(t("output_tab.handler_dialog.discord_username"))
        self.username_label.setToolTip(t("output_tab.handler_dialog.discord_username_tooltip"))
        self.avatar_url_label.setText(t("output_tab.handler_dialog.discord_avatar"))
        self.avatar_url_label.setToolTip(t("output_tab.handler_dialog.discord_avatar_tooltip"))
        self.message_label.setText(t("output_tab.handler_dialog.discord_message"))
        self.message_label.setToolTip(t("output_tab.handler_dialog.discord_message_tooltip"))
        self.appearance.retranslate()

    def load(self, settings: DiscordHandlerSettings) -> None:
        """Show some settings in the fields.

        Args:
            settings (DiscordHandlerSettings): The settings.
        """
        self.url_input.setText(settings.url)
        self.username_input.setText(settings.username or "")
        self.avatar_url_input.setText(settings.avatar_url or "")
        self.message_input.setText(settings.message or "")
        self.appearance.load(settings)

    def read(self) -> DiscordHandlerSettings:
        """Read the fields.

        Returns:
            DiscordHandlerSettings: Their settings.
        """
        return DiscordHandlerSettings.model_validate(
            {
                "url": self.url_input.text().strip(),
                "username": self.username_input.text().strip() or None,
                "avatar_url": self.avatar_url_input.text().strip() or None,
                "message": self.message_input.text().strip() or None,
                **self.appearance.values(),
            }
        )
