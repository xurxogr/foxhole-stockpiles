"""Load fonts and tell whether they can draw a text."""

import logging
from typing import Final

from PIL import ImageFont
from PIL.ImageFont import FreeTypeFont, TransposedFont
from PIL.ImageFont import ImageFont as BitmapFont

logger = logging.getLogger(__name__)

Font = FreeTypeFont | BitmapFont | TransposedFont

# Tried in order until one can draw the whole text. None is shipped with the app:
# one with Chinese would add several megabytes for the few that need it.
SYSTEM_FONTS: Final[tuple[str, ...]] = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/PingFang.ttc",
)

# Not a character, so a font draws it with the shape it has for anything it lacks.
_NOT_A_CHARACTER: Final[str] = "\U0010ffff"


def load_font(path: str, size: int) -> Font | None:
    """Load a font file.

    Args:
        path (str): The file.
        size (int): The size in pixels.

    Returns:
        Font | None: The font, or None if the file is missing or is not a font.
    """
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        logger.debug("Font %s is not available", path)
        return None


def _glyph(font: Font, character: str) -> tuple[tuple[int, int], bytes]:
    """Get the shape a font draws for a character.

    Args:
        font (Font): The font.
        character (str): The character.

    Returns:
        tuple[tuple[int, int], bytes]: Its size and pixels, to compare shapes.
    """
    mask = font.getmask(character)
    return mask.size, bytes(mask)


def covers(font: Font, text: str) -> bool:
    """Check that a font has every character of a text.

    Args:
        font (Font): The font.
        text (str): The text.

    Returns:
        bool: False if any character would come out as the shape of a missing one.
    """
    missing = _glyph(font=font, character=_NOT_A_CHARACTER)
    return all(
        _glyph(font=font, character=character) != missing
        for character in set(text)
        if not character.isspace()
    )
