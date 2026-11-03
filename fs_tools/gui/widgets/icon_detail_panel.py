"""Panel showing a template's details next to its highest resolution counterpart."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.i18n import t
from fs_tools.gui.utils.bgr_pixmap import bgr_to_pixmap
from fs_tools.models.icon_template import IconTemplate


class IconDetailPanel(QWidget):
    """Info labels, icon action buttons and the image comparison of the selected template."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the panel.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        info_layout = QHBoxLayout()
        self.info_label_left = self._create_info_label()
        self.info_label_right = self._create_info_label()
        info_columns_layout = QHBoxLayout()
        info_columns_layout.addWidget(self.info_label_left)
        info_columns_layout.addWidget(self.info_label_right)
        info_layout.addLayout(info_columns_layout, stretch=1)

        buttons_layout = QVBoxLayout()
        self.save_button = self._create_action_button(buttons_layout)
        self.replace_button = self._create_action_button(buttons_layout)
        self.delete_button = self._create_action_button(buttons_layout)
        info_layout.addLayout(buttons_layout)
        layout.addLayout(info_layout)

        self.image_group = QGroupBox()
        image_layout = QHBoxLayout(self.image_group)
        self.current_group, self.current_image = self._create_image_column()
        image_layout.addWidget(self.current_group)
        self.highest_group, self.highest_image = self._create_image_column()
        image_layout.addWidget(self.highest_group)
        layout.addWidget(self.image_group)

    @staticmethod
    def _create_info_label() -> QLabel:
        """Create one of the two info columns.

        Returns:
            QLabel: The empty, styled label.
        """
        label = QLabel()
        label.setFont(QFont("Arial", 10))
        label.setWordWrap(True)
        label.setStyleSheet(
            "QLabel { background-color: palette(alternate-base); padding: 10px; "
            "border: 1px solid palette(mid); }"
        )
        return label

    @staticmethod
    def _create_action_button(layout: QVBoxLayout) -> QPushButton:
        """Create a disabled action button and add it to the layout.

        Args:
            layout (QVBoxLayout): The layout holding the buttons.

        Returns:
            QPushButton: The button.
        """
        button = QPushButton()
        button.setEnabled(False)
        button.setMinimumWidth(120)
        layout.addWidget(button)
        return button

    @staticmethod
    def _create_image_column() -> tuple[QGroupBox, QLabel]:
        """Create a titled, scrollable image display.

        Returns:
            tuple[QGroupBox, QLabel]: The group box and the label showing the image.
        """
        group = QGroupBox()
        group_layout = QVBoxLayout(group)
        scroll = QScrollArea()
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setMinimumHeight(200)
        image.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); background-color: palette(base); }"
        )
        scroll.setWidget(image)
        scroll.setWidgetResizable(True)
        group_layout.addWidget(scroll)
        return group, image

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.info_label_left.setText(t("database_visualizer.select_template"))
        self.info_label_right.setText("")
        self.save_button.setText(t("database_visualizer.save_icon"))
        self.replace_button.setText(t("database_visualizer.replace_icon"))
        self.delete_button.setText(t("database_visualizer.delete_icon"))
        self.image_group.setTitle(t("database_visualizer.template_comparison"))
        self.current_group.setTitle(t("database_visualizer.current_resolution"))
        self.highest_group.setTitle(t("database_visualizer.highest_resolution"))
        self.current_image.setText(t("database_visualizer.no_image_selected"))
        self.highest_image.setText(t("database_visualizer.no_image_selected"))

    def set_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable the icon action buttons.

        Args:
            enabled (bool): Whether the buttons can be used.
        """
        self.save_button.setEnabled(enabled)
        self.replace_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def clear_details(self) -> None:
        """Go back to showing that no template is selected."""
        self.info_label_left.setText(t("database_visualizer.select_template"))
        self.info_label_right.setText("")
        self.current_image.clear()
        self.current_image.setText(t("database_visualizer.no_image_selected"))
        self.highest_image.clear()
        self.highest_image.setText(t("database_visualizer.no_image_selected"))

    def show_template(
        self,
        index: int,
        template: IconTemplate,
        highest_template: IconTemplate | None,
        highest_resolution: SupportedResolution,
    ) -> None:
        """Show a template's details and images.

        Args:
            index (int): The template's position in its resolution.
            template (IconTemplate): The selected template.
            highest_template (IconTemplate | None): The same icon at the highest resolution.
            highest_resolution (SupportedResolution): The highest resolution available.
        """
        self.info_label_left.setText(
            f"<b>{t('database_visualizer.info.code')}</b> {escape(template.code)}<br>"
            f"<b>{t('database_visualizer.info.faction')}</b> {template.faction.value}<br>"
            f"<b>{t('database_visualizer.info.category')}</b> {template.category.value}<br>"
            f"<b>{t('database_visualizer.info.mod')}</b> {escape(template.mod)}<br>"
            f"<b>{t('database_visualizer.info.crated')}</b> {template.crated}"
        )

        current_res = f"{template.resolution.value}px"
        if highest_template:
            highest_info = (
                f"<b>{t('database_visualizer.info.highest_res_available')}</b> "
                f"{highest_template.resolution.value}px ({highest_template.image.shape})"
            )
        else:
            not_found_msg = t(
                "database_visualizer.info.highest_res_not_found",
                resolution=highest_resolution.value,
            )
            highest_info = f"<b>{not_found_msg}</b>"

        self.info_label_right.setText(
            f"<b>{t('database_visualizer.info.current_resolution')}</b> {current_res}<br>"
            f"<b>{t('database_visualizer.info.current_shape')}</b> {template.image.shape}<br>"
            f"<b>{t('database_visualizer.info.database_index')}</b> {index}<br>"
            f"{highest_info}"
        )

        self.display_comparison_images(template, highest_template)

    @staticmethod
    def _scale_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
        """Scale a pixmap to the given size, keeping aspect ratio.

        Args:
            pixmap (QPixmap): The pixmap to scale.
            width (int): Target width.
            height (int): Target height.

        Returns:
            QPixmap: The scaled pixmap.
        """
        return pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    def display_comparison_images(
        self, current_template: IconTemplate | None, highest_template: IconTemplate | None
    ) -> None:
        """Display current and highest resolution templates at matching sizes.

        Args:
            current_template (IconTemplate | None): The currently selected template.
            highest_template (IconTemplate | None): The highest resolution template.
        """
        if not current_template:
            return

        current_pixmap = bgr_to_pixmap(current_template.image)
        current_w, current_h = current_pixmap.width(), current_pixmap.height()

        if highest_template:
            highest_pixmap = bgr_to_pixmap(highest_template.image)

            # Target size: highest resolution at 4x scale
            target_width = highest_pixmap.width() * 4
            target_height = highest_pixmap.height() * 4

            # Keep aspect ratio when scaling current resolution to match target size
            current_scale = min(target_width / current_w, target_height / current_h)
            current_scaled = self._scale_pixmap(
                current_pixmap, int(current_w * current_scale), int(current_h * current_scale)
            )
            highest_scaled = self._scale_pixmap(highest_pixmap, target_width, target_height)

            self.highest_image.setPixmap(highest_scaled)
            self.highest_image.resize(highest_scaled.size())
            self.highest_group.setTitle(
                t(
                    "database_visualizer.highest_resolution_found",
                    resolution=highest_template.resolution.value,
                )
            )
        else:
            # Fallback: use 8x for current if no highest template
            current_scale = 8.0
            current_scaled = self._scale_pixmap(
                current_pixmap, int(current_w * current_scale), int(current_h * current_scale)
            )

            self.highest_image.setText(t("database_visualizer.template_not_found"))
            self.highest_group.setTitle(t("database_visualizer.highest_resolution_not_found"))

        self.current_image.setPixmap(current_scaled)
        self.current_image.resize(current_scaled.size())
        self.current_group.setTitle(
            t(
                "database_visualizer.current_resolution_scale",
                resolution=current_template.resolution.value,
                scale=f"{current_scale:.1f}",
            )
        )
