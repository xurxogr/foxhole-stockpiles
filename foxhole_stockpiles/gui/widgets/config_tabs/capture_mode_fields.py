"""Fields shared by the tabs configuring a capture method that can be monitored."""

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox

from foxhole_stockpiles.core.constants import MAX_POLL_INTERVAL, MIN_POLL_INTERVAL
from foxhole_stockpiles.enums.capture_mode import CaptureMode


def build_mode_combo() -> QComboBox:
    """Build the selector of the capture mode; the tab translates its items.

    Returns:
        QComboBox: The selector, with manual first and monitor second.
    """
    combo = QComboBox()
    combo.addItem("", CaptureMode.MANUAL)
    combo.addItem("", CaptureMode.MONITOR)
    return combo


def build_poll_interval_input() -> QDoubleSpinBox:
    """Build the input of the polling interval.

    Returns:
        QDoubleSpinBox: The input, in seconds.
    """
    spin = QDoubleSpinBox()
    spin.setRange(MIN_POLL_INTERVAL, MAX_POLL_INTERVAL)
    spin.setSingleStep(0.5)
    spin.setDecimals(1)
    spin.setSuffix(" s")
    return spin
