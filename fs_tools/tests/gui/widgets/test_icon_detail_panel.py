"""The info labels are rich text, and what they show comes from the database file."""

from typing import Any

import numpy as np

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.gui.widgets.icon_detail_panel import IconDetailPanel
from fs_tools.models.icon_template import IconTemplate

_MARKUP = "<img src='x'>&"
_ESCAPED = "&lt;img src=&#x27;x&#x27;&gt;&amp;"


def test_template_text_is_shown_as_text_and_not_as_markup(qtbot: Any) -> None:
    """A code or mod name holding markup is displayed literally."""
    panel = IconDetailPanel()
    qtbot.addWidget(panel)
    template = IconTemplate(
        code=_MARKUP,
        faction=ItemFaction.NEUTRAL,
        category=ItemCategory.Item,
        mod=_MARKUP,
        resolution=SupportedResolution.R_1080,
        image=np.zeros((32, 32, 3), dtype=np.uint8),
    )

    panel.show_template(
        index=0,
        template=template,
        highest_template=None,
        highest_resolution=SupportedResolution.R_1080,
    )

    text = panel.info_label_left.text()
    assert _MARKUP not in text
    assert text.count(_ESCAPED) == 2
