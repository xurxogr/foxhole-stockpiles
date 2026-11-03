"""One line of a stockpile image."""

from pydantic import BaseModel, ConfigDict


class ImageLine(BaseModel):
    """A category heading, or an item row when it has a code.

    Attributes:
        text (str): The heading, or the name of the item.
        code (str | None): The code of the item; None in a heading.
        quantity (str | None): The quantity as shown; None in a heading.
        crated (bool): Whether the item is in crates.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    code: str | None = None
    quantity: str | None = None
    crated: bool = False

    @property
    def is_heading(self) -> bool:
        """Whether this line is a category heading.

        Returns:
            bool: True if it has no item.
        """
        return self.code is None
