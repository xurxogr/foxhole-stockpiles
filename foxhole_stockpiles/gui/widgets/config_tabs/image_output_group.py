"""The fields of the handler that saves stockpiles as images."""

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from foxhole_stockpiles.core.settings.sections.output import ImageHandlerSettings
from foxhole_stockpiles.gui.widgets.config_tabs.image_appearance_fields import (
    ImageAppearanceFields,
)
from foxhole_stockpiles.i18n import t


class ImageOutputGroup(QGroupBox):
    """Where to save the images, and how to draw them."""

    def __init__(self) -> None:
        """Create the fields."""
        super().__init__()
        form = QFormLayout()
        self.setLayout(form)

        self.path_label = QLabel()
        self.path_input = QLineEdit()
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_input)
        path_row.addWidget(self.browse_btn)
        form.addRow(self.path_label, path_row)

        self.appearance = ImageAppearanceFields(form)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setTitle(t("output_tab.handler_dialog.image_settings"))
        self.path_label.setText(t("output_tab.handler_dialog.image_path"))
        self.path_label.setToolTip(t("output_tab.handler_dialog.image_path_tooltip"))
        self.path_input.setPlaceholderText(t("output_tab.handler_dialog.image_path_placeholder"))
        self.browse_btn.setText(t("common.browse"))
        self.appearance.retranslate()

    def load(self, settings: ImageHandlerSettings) -> None:
        """Show some settings in the fields.

        Args:
            settings (ImageHandlerSettings): The settings.
        """
        self.path_input.setText(settings.path)
        self.appearance.load(settings)

    def read(self) -> ImageHandlerSettings:
        """Read the fields.

        Returns:
            ImageHandlerSettings: Their settings.
        """
        return ImageHandlerSettings.model_validate(
            {"path": self.path_input.text().strip(), **self.appearance.values()}
        )

    def _browse(self) -> None:
        """Choose where to save the images."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            t("output_tab.handler_dialog.image_path"),
            "",
            "PNG (*.png);;All Files (*)",
        )
        if filepath:
            self.path_input.setText(filepath)
