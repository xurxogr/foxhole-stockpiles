"""The fields that choose which stockpiles an output receives."""

from enum import StrEnum

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel

from foxhole_stockpiles.enums.public_stockpile_filter import PublicStockpileFilter
from foxhole_stockpiles.enums.stockpile_grouping import StockpileGrouping
from foxhole_stockpiles.i18n import t

_KEYS = "output_tab.handler_dialog"


def _combo(options: type[StrEnum]) -> QComboBox:
    """Create a list of the values of an enum, each one in its data.

    Args:
        options (type[StrEnum]): The enum.

    Returns:
        QComboBox: The list, with the first value selected.
    """
    combo = QComboBox()
    for option in options:
        combo.addItem(option.value, option.value)
    return combo


def _retranslate_combo(combo: QComboBox, key: str) -> None:
    """Name each option of a list in the language of the window.

    Args:
        combo (QComboBox): The list.
        key (str): The key of its texts, each option adding ``_<value>``.
    """
    for index in range(combo.count()):
        combo.setItemText(index, t(f"{key}_{combo.itemData(index)}"))


def _select(combo: QComboBox, value: str) -> None:
    """Select the option of a value.

    Args:
        combo (QComboBox): The list.
        value (str): The value.
    """
    combo.setCurrentIndex(max(combo.findData(value), 0))


class StockpileSelectionGroup(QGroupBox):
    """Which public stockpiles an output receives, and which ones as one."""

    def __init__(self) -> None:
        """Create the fields."""
        super().__init__()
        form = QFormLayout()
        self.setLayout(form)

        self.public_label = QLabel()
        self.public_input = _combo(PublicStockpileFilter)
        form.addRow(self.public_label, self.public_input)

        self.grouping_label = QLabel()
        self.grouping_input = _combo(StockpileGrouping)
        form.addRow(self.grouping_label, self.grouping_input)

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setTitle(t(f"{_KEYS}.selection_settings"))
        self.public_label.setText(t(f"{_KEYS}.public_stockpiles"))
        self.public_label.setToolTip(t(f"{_KEYS}.public_stockpiles_tooltip"))
        _retranslate_combo(self.public_input, f"{_KEYS}.public_stockpiles")
        self.grouping_label.setText(t(f"{_KEYS}.grouping"))
        self.grouping_label.setToolTip(t(f"{_KEYS}.grouping_tooltip"))
        _retranslate_combo(self.grouping_input, f"{_KEYS}.grouping")

    def load(self, public_stockpiles: PublicStockpileFilter, grouping: StockpileGrouping) -> None:
        """Show the selection of an output.

        Args:
            public_stockpiles (PublicStockpileFilter): Which public stockpiles it receives.
            grouping (StockpileGrouping): Which stockpiles it receives as one.
        """
        _select(self.public_input, public_stockpiles.value)
        _select(self.grouping_input, grouping.value)

    def values(self) -> dict[str, str]:
        """Read the fields.

        Returns:
            dict[str, str]: The values of the settings they edit.
        """
        return {
            "public_stockpiles": self.public_input.currentData(),
            "grouping": self.grouping_input.currentData(),
        }
