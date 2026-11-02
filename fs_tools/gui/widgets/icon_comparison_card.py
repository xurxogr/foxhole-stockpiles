"""Card showing one icon with its labels and match score, enlarged for comparison."""

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from foxhole_stockpiles.core.image_io import resize_bgr
from fs_tools.gui.utils.bgr_pixmap import bgr_to_pixmap


class IconComparisonCard(QWidget):
    """An icon at 4x scale above its label, optional sublabel and NCC score."""

    def __init__(
        self,
        image: np.ndarray,
        label: str,
        sublabel: str | None,
        ncc_score: float | None,
        target_size: int,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the card.

        Args:
            image (np.ndarray): Image to display (BGR format).
            label (str): Label text (e.g., mod name or "Detected").
            sublabel (str | None): Second line label text (e.g., code name or pHash dist).
            ncc_score (float | None): NCC score to display, or None for detected icon.
            target_size (int): Target size for scaling.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Scale image to 4x for visibility
        scale = 4
        scaled_size = target_size * scale

        # Resize image if needed to match target size first
        if image.shape[0] != target_size or image.shape[1] != target_size:
            image = resize_bgr(image, target_size, target_size, mode="area")

        # Scale up for display
        display_image = resize_bgr(image, scaled_size, scaled_size, mode="nearest")

        # Icon image
        image_label = QLabel()
        image_label.setPixmap(bgr_to_pixmap(display_image))
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("QLabel { border: 1px solid palette(mid); }")
        layout.addWidget(image_label)

        # Label text (line 1)
        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(text_label)

        # Sublabel (line 2)
        if sublabel:
            sublabel_widget = QLabel(sublabel)
            sublabel_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sublabel_widget.setStyleSheet("QLabel { color: palette(mid); }")
            layout.addWidget(sublabel_widget)

        # NCC score (line 3) - add spacer if None to keep alignment
        score_label = QLabel()
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if ncc_score is not None:
            score_label.setText(f"NCC: {ncc_score:.3f}")
            # Color based on score
            if ncc_score >= 0.95:
                color = "#4caf50"  # Green
            elif ncc_score >= 0.90:
                color = "#ff9800"  # Orange
            else:
                color = "#f44336"  # Red
            score_label.setStyleSheet(f"QLabel {{ color: {color}; }}")
        else:
            score_label.setText(" ")  # Spacer for alignment
        layout.addWidget(score_label)
