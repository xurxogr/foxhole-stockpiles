"""Choose the font that draws each text of an image."""

from typing import cast

from PIL import ImageFont

from foxhole_stockpiles.services.stockpile_image import fonts
from foxhole_stockpiles.services.stockpile_image.fonts import Font


class FontSelector:
    """Finds a font for each text, as a name may be in any alphabet."""

    def __init__(self, font_path: str | None = None) -> None:
        """Initialize the selector.

        Args:
            font_path (str | None): A font to try before those of the system.
        """
        self._font_path = font_path
        self._loaded: dict[tuple[str, int], Font | None] = {}

    def _available_fonts(self, size: int) -> list[Font]:
        """Load the fonts this system has, in the order they are tried.

        Args:
            size (int): The size in pixels.

        Returns:
            list[Font]: Those that could be loaded.
        """
        paths = [self._font_path] if self._font_path else []
        available: list[Font] = []
        for path in [*paths, *fonts.SYSTEM_FONTS]:
            key = (path, size)
            if key not in self._loaded:
                self._loaded[key] = fonts.load_font(path=path, size=size)
            loaded = self._loaded[key]
            if loaded is not None:
                available.append(loaded)
        return available

    def font_for(self, text: str, size: int) -> Font:
        """Choose the font for a text.

        Args:
            text (str): The text to draw.
            size (int): The size in pixels.

        Returns:
            Font: The first font with all its characters, or else the first available.
        """
        available = self._available_fonts(size)
        for font in available:
            if fonts.covers(font=font, text=text):
                return font
        # Pillow's own font only has Latin characters, but it is always there.
        return available[0] if available else cast(Font, ImageFont.load_default(size=size))
