"""Decide where each item of a stockpile goes, without drawing anything."""

import math
from typing import Final, Protocol

from foxhole_stockpiles.models.image_line import ImageLine
from foxhole_stockpiles.models.image_page import ImagePage
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem

# A taller or wider image is scaled down by chat clients until it can't be read.
MAX_COLUMN_LINES: Final[int] = 32
MAX_PAGE_COLUMNS: Final[int] = 4

UNKNOWN_QUANTITY: Final[str] = "?"

_OTHER_CATEGORY: Final[str] = "Other"
_CRATES_SUFFIX: Final[str] = " (crates)"
# In supply order, so related goods read together. Anything else goes after these.
_CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "Small Arms",
    "Heavy Arms",
    "Heavy Ammo",
    "Utility",
    "Medical",
    "Supplies",
    "Parts",
    "Uniforms",
    "Vehicles",
    "Structures",
)


class ItemNames(Protocol):
    """What the layout needs to know about the items."""

    def get_display_name(self, code: str) -> str:
        """Get the name shown for an item.

        Args:
            code (str): The code of the item.

        Returns:
            str: Its name.
        """
        ...

    def get_category(self, code: str) -> str | None:
        """Get the category of an item.

        Args:
            code (str): The code of the item.

        Returns:
            str | None: Its category, if it has one.
        """
        ...


def _category_rank(category: str) -> tuple[int, str]:
    """Build the sort key of a category.

    Args:
        category (str): The category, without the crates suffix.

    Returns:
        tuple[int, str]: Its place in the supply order, then its name.
    """
    if category == _OTHER_CATEGORY:
        return len(_CATEGORY_ORDER) + 1, category
    if category in _CATEGORY_ORDER:
        return _CATEGORY_ORDER.index(category), category
    return len(_CATEGORY_ORDER), category


def _item_line(item: StockpileItem, name: str) -> ImageLine:
    """Build the row of an item.

    Args:
        item (StockpileItem): The item.
        name (str): The name to show.

    Returns:
        ImageLine: Its row.
    """
    quantity = UNKNOWN_QUANTITY if item.quantity < 0 else str(item.quantity)
    return ImageLine(text=name, code=item.code, quantity=quantity, crated=item.crated)


def _build_groups(stockpile: Stockpile, catalog: ItemNames) -> list[tuple[str, list[ImageLine]]]:
    """Group the items of a stockpile by category, crates apart from loose items.

    Args:
        stockpile (Stockpile): The stockpile.
        catalog (ItemNames): Where the names and categories come from.

    Returns:
        list[tuple[str, list[ImageLine]]]: Each heading with its rows, in display order.
    """
    groups: dict[tuple[str, bool], list[ImageLine]] = {}
    for item in stockpile.items:
        category = catalog.get_category(item.code) or _OTHER_CATEGORY
        line = _item_line(item=item, name=catalog.get_display_name(item.code))
        groups.setdefault((category, item.crated), []).append(line)

    ordered = sorted(groups, key=lambda key: (_category_rank(key[0]), key[1]))
    return [
        (
            f"{category}{_CRATES_SUFFIX}" if crated else category,
            sorted(groups[(category, crated)], key=lambda line: line.text.casefold()),
        )
        for category, crated in ordered
    ]


def _column_height(groups: list[tuple[str, list[ImageLine]]]) -> int:
    """Choose how many lines a column holds, so that the columns come out even.

    Args:
        groups (list[tuple[str, list[ImageLine]]]): Each heading with its rows.

    Returns:
        int: The lines of a column, at most the limit.
    """
    total = sum(len(rows) + 1 for _, rows in groups)
    if total > MAX_COLUMN_LINES * MAX_PAGE_COLUMNS:
        return MAX_COLUMN_LINES
    columns = max(1, math.ceil(total / MAX_COLUMN_LINES))
    # Each column after the first may repeat the heading of a group that continues.
    return min(MAX_COLUMN_LINES, max(2, math.ceil((total + columns - 1) / columns)))


def _build_columns(groups: list[tuple[str, list[ImageLine]]], height: int) -> list[list[ImageLine]]:
    """Fill columns with the groups, repeating a heading where its group continues.

    Args:
        groups (list[tuple[str, list[ImageLine]]]): Each heading with its rows.
        height (int): The lines of a column, at least two.

    Returns:
        list[list[ImageLine]]: The lines of each column.
    """
    columns: list[list[ImageLine]] = []
    current: list[ImageLine] = []
    for heading_text, rows in groups:
        heading = ImageLine(text=heading_text)
        # A heading needs room for its first row as well.
        if current and len(current) + 2 > height:
            columns.append(current)
            current = []
        current = [*current, heading]
        for row in rows:
            if len(current) == height:
                columns.append(current)
                current = [heading]
            current = [*current, row]
    return [*columns, current] if current else columns


def build_pages(stockpile: Stockpile, catalog: ItemNames) -> list[ImagePage]:
    """Lay out the items of a stockpile in pages of columns.

    Args:
        stockpile (Stockpile): The stockpile.
        catalog (ItemNames): Where the names and categories come from.

    Returns:
        list[ImagePage]: At least one page, without columns if it has no items.
    """
    groups = _build_groups(stockpile=stockpile, catalog=catalog)
    columns = _build_columns(groups=groups, height=_column_height(groups))
    pages = [
        ImagePage(columns=columns[start : start + MAX_PAGE_COLUMNS])
        for start in range(0, len(columns), MAX_PAGE_COLUMNS)
    ]
    return pages or [ImagePage(columns=[])]
