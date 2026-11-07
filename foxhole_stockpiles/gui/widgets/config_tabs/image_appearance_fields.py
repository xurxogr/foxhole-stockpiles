"""The fields of how a stockpile is drawn, shared by the handlers that draw images."""

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.i18n import get_available_languages, t
from foxhole_stockpiles.services.stockpile_image.icons import BASE_GAME_MOD, list_icon_mods
from foxhole_stockpiles.services.stockpile_image.image_text import DEFAULT_LANGUAGE


class ImageAppearanceFields:
    """Adds the language, icon mod and font fields to the form of a handler."""

    def __init__(self, form: QFormLayout) -> None:
        """Create the fields.

        Args:
            form (QFormLayout): The form they are added to.
        """
        self.language_label = QLabel()
        self.language_input = QComboBox()
        for code, name in get_available_languages():
            self.language_input.addItem(name, code)
        self._select_language(DEFAULT_LANGUAGE)
        form.addRow(self.language_label, self.language_input)

        self.icon_mod_label = QLabel()
        self.icon_mod_input = QComboBox()
        # Editable: the mod may not be in the database yet, or the database not set.
        self.icon_mod_input.setEditable(True)
        mods = list_icon_mods(get_settings().scanner.database_path)
        self.icon_mod_input.addItems(mods or [BASE_GAME_MOD])
        self.icon_mod_input.setCurrentText(BASE_GAME_MOD)
        form.addRow(self.icon_mod_label, self.icon_mod_input)

        self.font_path_label = QLabel()
        self.font_path_input = QLineEdit()
        self.font_browse_btn = QPushButton()
        self.font_browse_btn.clicked.connect(self._browse_font)
        font_row = QWidget()
        font_layout = QHBoxLayout(font_row)
        font_layout.setContentsMargins(0, 0, 0, 0)
        font_layout.addWidget(self.font_path_input)
        font_layout.addWidget(self.font_browse_btn)
        form.addRow(self.font_path_label, font_row)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.language_label.setText(t("output_tab.handler_dialog.image_language"))
        self.language_label.setToolTip(t("output_tab.handler_dialog.image_language_tooltip"))
        self.icon_mod_label.setText(t("output_tab.handler_dialog.image_icon_mod"))
        self.icon_mod_label.setToolTip(t("output_tab.handler_dialog.image_icon_mod_tooltip"))
        self.font_path_label.setText(t("output_tab.handler_dialog.image_font"))
        self.font_path_label.setToolTip(t("output_tab.handler_dialog.image_font_tooltip"))
        self.font_browse_btn.setText(t("common.browse"))

    def load(self, settings: StockpileImageSettings) -> None:
        """Show some settings in the fields.

        Args:
            settings (StockpileImageSettings): The settings.
        """
        self._select_language(settings.language)
        self.icon_mod_input.setCurrentText(settings.icon_mod)
        self.font_path_input.setText(settings.font_path or "")

    def values(self) -> dict[str, str | None]:
        """Read the fields.

        Returns:
            dict[str, str | None]: The values of the settings they edit.
        """
        return {
            "language": self.language_input.currentData(),
            "icon_mod": self.icon_mod_input.currentText().strip() or BASE_GAME_MOD,
            "font_path": self.font_path_input.text().strip() or None,
        }

    def _select_language(self, language: str) -> None:
        """Select a language, or the default one if it does not exist.

        Args:
            language (str): The language code.
        """
        index = self.language_input.findData(language)
        if index < 0:
            index = self.language_input.findData(DEFAULT_LANGUAGE)
        self.language_input.setCurrentIndex(index)

    def _browse_font(self) -> None:
        """Choose the font file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self.font_browse_btn,
            t("output_tab.handler_dialog.image_font"),
            "",
            "Fonts (*.ttf *.ttc *.otf);;All Files (*)",
        )
        if filepath:
            self.font_path_input.setText(filepath)
