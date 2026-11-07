"""The text that names a group of stockpiles."""

from typing import Protocol


class GroupLabels(Protocol):
    """What naming a merge needs, in the language of its output."""

    def all_stockpiles(self) -> str:
        """Get the name of the merge of several stockpiles.

        Returns:
            str: The name.
        """
        ...
