"""The text of a stockpile image, in the language of its output.

It does not use the language of the window: the person who reads a channel is not
necessarily the one who runs the application.
"""

import logging
from typing import Final, Protocol

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.i18n import Translator, get_available_languages

DEFAULT_LANGUAGE: Final[str] = "en"

_KEYS: Final[str] = "stockpile_image"
# Names from the game, copied by ``fs-tools import-display-names``.
_TYPE_KEYS: Final[str] = "stockpile_types"

logger = logging.getLogger(__name__)


class LocalizedCatalog(Protocol):
    """What the text of an image needs to know about the items."""

    def get_display_name(self, code: str, language: str | None = None) -> str:
        """Get the name of an item.

        Args:
            code (str): The code of the item.
            language (str | None): The language of the name.

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


def _known_language(language: str) -> str:
    """Check a language, as the configuration can be edited by hand.

    Args:
        language (str): The language code.

    Returns:
        str: The same code, or the default one if there is no such language.
    """
    if language in {code for code, _name in get_available_languages()}:
        return language
    logger.warning("There is no language '%s' for images, using English", language)
    return DEFAULT_LANGUAGE


class ImageText:
    """Gives every text of an image in one language."""

    def __init__(self, catalog: LocalizedCatalog, language: str) -> None:
        """Initialize the texts.

        Args:
            catalog (LocalizedCatalog): Where the items come from.
            language (str): The language code.
        """
        self._catalog = catalog
        self._language = _known_language(language)
        self._translator = Translator(self._language)

    def _lookup(self, key: str, default: str) -> str:
        """Read a text that may not exist.

        Args:
            key (str): Its key, inside those of the images.
            default (str): What to show without it.

        Returns:
            str: The text.
        """
        full_key = f"{_KEYS}.{key}"
        text = self._translator.get(full_key)
        return default if text == full_key else text

    def get_display_name(self, code: str) -> str:
        """Get the name of an item, in English if the game has none in this language.

        Args:
            code (str): The code of the item.

        Returns:
            str: Its name.
        """
        return self._catalog.get_display_name(code=code, language=self._language)

    def get_category(self, code: str) -> str | None:
        """Get the category of an item, which orders the groups in any language.

        Args:
            code (str): The code of the item.

        Returns:
            str | None: Its category, if it has one.
        """
        return self._catalog.get_category(code)

    def category_heading(self, category: str, crated: bool) -> str:
        """Get the heading of a group of items.

        Args:
            category (str): The category.
            crated (bool): Whether the group holds crates.

        Returns:
            str: The heading.
        """
        key = category.lower().replace(" ", "_")
        name = self._lookup(key=f"categories.{key}", default=category)
        if not crated:
            return name
        return self._translator.get(f"{_KEYS}.crates", category=name)

    def stockpile_type(self, stockpile_type: str) -> str:
        """Get the name of a type of stockpile.

        Args:
            stockpile_type (str): The type.

        Returns:
            str: Its name, empty if it is not known. A type this version has no name
                for is shown as it came.
        """
        if not stockpile_type or stockpile_type == StockpileType.UNDEFINED:
            return ""
        key = f"{_TYPE_KEYS}.{stockpile_type}"
        name = self._translator.get(key)
        return str(stockpile_type) if name == key else name

    def all_stockpiles(self) -> str:
        """Get the name of the merge of several stockpiles.

        Returns:
            str: The name.
        """
        return self._translator.get(f"{_KEYS}.all_stockpiles")

    def no_items(self) -> str:
        """Get what an empty stockpile shows.

        Returns:
            str: The text.
        """
        return self._translator.get(f"{_KEYS}.no_items")

    def total(self, quantity: int) -> str:
        """Get the total of a stockpile.

        Args:
            quantity (int): The total.

        Returns:
            str: The text.
        """
        return self._translator.get(f"{_KEYS}.total", quantity=quantity)
