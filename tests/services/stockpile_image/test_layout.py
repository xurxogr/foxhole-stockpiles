"""Where each item of a stockpile goes in its images."""

from typing import Any

from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.stockpile_image import layout
from foxhole_stockpiles.services.stockpile_image.layout import build_pages


class _Catalog:
    """A catalog where each code names its category as `Category/name`."""

    def get_display_name(self, code: str) -> str:
        """Get the name in the code.

        Args:
            code (str): The code.

        Returns:
            str: The part after the slash.
        """
        return code.rpartition("/")[2]

    def get_category(self, code: str) -> str | None:
        """Get the category in the code.

        Args:
            code (str): The code.

        Returns:
            str | None: The part before the slash, or None without one.
        """
        category, slash, _ = code.partition("/")
        return category if slash else None

    def category_heading(self, category: str, crated: bool) -> str:
        """Get the heading of a group.

        Args:
            category (str): The category.
            crated (bool): Whether the group holds crates.

        Returns:
            str: The category, marked when it holds crates.
        """
        return f"{category} (crates)" if crated else category


def _pages(*items: StockpileItem) -> list[Any]:
    return build_pages(stockpile=Stockpile(items=list(items)), catalog=_Catalog())


def _item(code: str, quantity: int = 1, crated: bool = False) -> StockpileItem:
    return StockpileItem(code=code, quantity=quantity, crated=crated)


def _texts(page: Any) -> list[list[str]]:
    return [[line.text for line in column] for column in page.columns]


def test_items_are_grouped_by_category_in_supply_order() -> None:
    """Related goods read together, with what has no category at the end."""
    pages = _pages(_item("Vehicles/Truck"), _item("Unknown"), _item("Small Arms/Rifle"))

    assert _texts(pages[0]) == [["Small Arms", "Rifle", "Vehicles", "Truck", "Other", "Unknown"]]


def test_crates_are_a_separate_group_after_the_loose_items() -> None:
    """A crate of rifles is not the same good as a loose rifle."""
    pages = _pages(_item("Small Arms/Rifle", crated=True), _item("Small Arms/Rifle"))

    assert _texts(pages[0]) == [["Small Arms", "Rifle", "Small Arms (crates)", "Rifle"]]


def test_items_of_a_group_are_sorted_by_name() -> None:
    """The order does not depend on how the source listed them."""
    pages = _pages(_item("Small Arms/b"), _item("Small Arms/A"))

    assert _texts(pages[0])[0][1:] == ["A", "b"]


def test_quantity_is_shown_and_an_unknown_one_is_not_a_number() -> None:
    """An unreadable quantity stays visibly unknown."""
    pages = _pages(_item("Small Arms/a", quantity=7), _item("Small Arms/b", quantity=-1))

    assert [line.quantity for line in pages[0].columns[0]] == [None, "7", "?"]


def test_a_stockpile_without_items_has_one_empty_page() -> None:
    """It still produces an image, saying that it is empty."""
    pages = _pages()

    assert len(pages) == 1
    assert pages[0].columns == []


def test_a_long_group_continues_in_the_next_column_under_its_heading(monkeypatch: Any) -> None:
    """No column grows past the limit, and it is clear what each one holds."""
    monkeypatch.setattr(layout, "MAX_COLUMN_LINES", 3)
    monkeypatch.setattr(layout, "MAX_PAGE_COLUMNS", 10)

    pages = _pages(*(_item(f"Small Arms/{name}") for name in "abcde"))

    assert _texts(pages[0]) == [
        ["Small Arms", "a", "b"],
        ["Small Arms", "c", "d"],
        ["Small Arms", "e"],
    ]


def test_a_heading_is_never_left_alone_at_the_end_of_a_column(monkeypatch: Any) -> None:
    """A heading goes with its first item."""
    monkeypatch.setattr(layout, "MAX_COLUMN_LINES", 3)
    monkeypatch.setattr(layout, "MAX_PAGE_COLUMNS", 10)

    pages = _pages(_item("Small Arms/a"), _item("Vehicles/b"))

    assert _texts(pages[0]) == [["Small Arms", "a"], ["Vehicles", "b"]]


def test_columns_are_split_into_pages(monkeypatch: Any) -> None:
    """A huge stockpile becomes several images that can be read."""
    monkeypatch.setattr(layout, "MAX_COLUMN_LINES", 3)
    monkeypatch.setattr(layout, "MAX_PAGE_COLUMNS", 2)

    pages = _pages(*(_item(f"Small Arms/{name}") for name in "abcdef"))

    assert [len(page.columns) for page in pages] == [2, 1]


def test_lines_are_balanced_between_the_columns(monkeypatch: Any) -> None:
    """A short last column does not hang next to full ones."""
    monkeypatch.setattr(layout, "MAX_COLUMN_LINES", 8)
    monkeypatch.setattr(layout, "MAX_PAGE_COLUMNS", 4)

    pages = _pages(*(_item(f"Small Arms/{index:02}") for index in range(9)))

    assert [len(column) for column in pages[0].columns] == [6, 5]
