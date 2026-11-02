"""The window members that the template icon actions work with."""

from typing import Protocol

from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.icon_template import IconTemplate


class TemplateIconView(Protocol):
    """What a window must offer for its selected template icon to be edited."""

    selected_template: tuple[int, IconTemplate] | None
    current_resolution: SupportedResolution | None
    database_path: str | None

    def reload_current_resolution(self) -> None:
        """Re-read the current resolution's templates after an edit and refresh the list."""
        ...

    def clear_selection(self) -> None:
        """Forget the selected template and clear its details."""
        ...
