"""The clipboard and .sav tabs configure their monitoring with the same fields."""

from typing import Any

from foxhole_stockpiles.core.constants import MAX_POLL_INTERVAL, MIN_POLL_INTERVAL
from foxhole_stockpiles.enums.capture_mode import CaptureMode
from foxhole_stockpiles.gui.widgets.config_tabs.capture_mode_fields import (
    build_mode_combo,
    build_poll_interval_input,
)


def test_mode_combo_offers_each_mode(qtbot: Any) -> None:
    """Both modes are offered, in the order the translations are applied."""
    combo = build_mode_combo()
    qtbot.addWidget(combo)

    assert [combo.itemData(i) for i in range(combo.count())] == [
        CaptureMode.MANUAL,
        CaptureMode.MONITOR,
    ]


def test_poll_interval_accepts_what_the_settings_accept(qtbot: Any) -> None:
    """The input can't produce a value the settings would refuse."""
    spin = build_poll_interval_input()
    qtbot.addWidget(spin)

    assert (spin.minimum(), spin.maximum()) == (MIN_POLL_INTERVAL, MAX_POLL_INTERVAL)
