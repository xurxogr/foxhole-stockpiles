"""Draw the pages of a stockpile image."""

import io
from typing import Final

from PIL import Image, ImageDraw

from foxhole_stockpiles.models.image_line import ImageLine
from foxhole_stockpiles.models.image_page import ImagePage
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.stockpile_image.font_selector import FontSelector
from foxhole_stockpiles.services.stockpile_image.fonts import Font
from foxhole_stockpiles.services.stockpile_image.icons import ICON_SIZE, IconKey
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText
from foxhole_stockpiles.services.stockpile_image.layout import build_pages
from foxhole_stockpiles.services.stockpile_image.placeholders import total_quantity

ROW_HEIGHT: Final[int] = 40

_COLUMN_WIDTH: Final[int] = 380
_COLUMN_GAP: Final[int] = 24
_MARGIN: Final[int] = 24
_HEADER_HEIGHT: Final[int] = 92
_FOOTER_HEIGHT: Final[int] = 48
_ROW_GAP: Final[int] = 4
_TEXT_PADDING: Final[int] = 10
_ELLIPSIS: Final[str] = "..."

_TITLE_SIZE: Final[int] = 28
_SUBTITLE_SIZE: Final[int] = 18
_HEADING_SIZE: Final[int] = 20
_ROW_TEXT_SIZE: Final[int] = 18

_BACKGROUND: Final = (17, 24, 39)
_ROW_BACKGROUND: Final = (30, 41, 59)
_TEXT: Final = (243, 244, 246)
_MUTED_TEXT: Final = (156, 163, 175)
_HEADING_TEXT: Final = (147, 197, 253)


def shorten(text: str, font: Font, max_width: int) -> str:
    """Cut a text so that it fits, saying that it was cut.

    Args:
        text (str): The text.
        font (Font): The font it is drawn with.
        max_width (int): The room there is, in pixels.

    Returns:
        str: The text, or the longest start of it that fits with an ellipsis.
    """
    if font.getlength(text) <= max_width:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font.getlength(text[:middle] + _ELLIPSIS) <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + _ELLIPSIS


class StockpileImageRenderer:
    """Draws a stockpile as one PNG per page."""

    def __init__(
        self,
        text: ImageText,
        font_selector: FontSelector,
        icons: dict[IconKey, Image.Image],
    ) -> None:
        """Initialize the renderer.

        Args:
            text (ImageText): The texts, in the language of the image.
            font_selector (FontSelector): What chooses the font of each text.
            icons (dict[IconKey, Image.Image]): The icon of each (code, crated).
        """
        self._labels = text
        self._fonts = font_selector
        self._icons = icons

    def render_png(self, stockpile: Stockpile, headline: str | None) -> list[bytes]:
        """Draw a stockpile.

        Args:
            stockpile (Stockpile): The stockpile.
            headline (str | None): The title, by default its name or else its type.

        Returns:
            list[bytes]: The PNG of each page.
        """
        pages = build_pages(stockpile=stockpile, catalog=self._labels)
        title = headline or stockpile.name or self._labels.stockpile_type(stockpile.type)
        return [
            self._encode(
                self._draw_page(
                    page=page,
                    stockpile=stockpile,
                    title=title,
                    page_label=f"{number}/{len(pages)}" if len(pages) > 1 else "",
                )
            )
            for number, page in enumerate(pages, start=1)
        ]

    @staticmethod
    def _encode(image: Image.Image) -> bytes:
        """Encode an image as a PNG.

        Args:
            image (Image.Image): The image.

        Returns:
            bytes: The PNG.
        """
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _draw_page(
        self, page: ImagePage, stockpile: Stockpile, title: str, page_label: str
    ) -> Image.Image:
        """Draw one page.

        Args:
            page (ImagePage): Its columns.
            stockpile (Stockpile): The stockpile.
            title (str): The title.
            page_label (str): Which page it is, empty if there is only one.

        Returns:
            Image.Image: The page.
        """
        columns = max(1, len(page.columns))
        lines = max((len(column) for column in page.columns), default=1)
        width = 2 * _MARGIN + columns * _COLUMN_WIDTH + (columns - 1) * _COLUMN_GAP
        height = _HEADER_HEIGHT + lines * ROW_HEIGHT + _FOOTER_HEIGHT

        image = Image.new("RGB", (width, height), _BACKGROUND)
        draw = ImageDraw.Draw(image)
        self._draw_header(draw=draw, stockpile=stockpile, title=title, width=width)
        for index, column in enumerate(page.columns):
            x = _MARGIN + index * (_COLUMN_WIDTH + _COLUMN_GAP)
            for row, line in enumerate(column):
                self._draw_line(
                    image=image, draw=draw, line=line, x=x, y=_HEADER_HEIGHT + row * ROW_HEIGHT
                )
        if not page.columns:
            self._text(
                draw,
                xy=(_MARGIN, _HEADER_HEIGHT),
                text=self._labels.no_items(),
                size=_ROW_TEXT_SIZE,
            )
        self._draw_footer(
            draw=draw, stockpile=stockpile, page_label=page_label, width=width, height=height
        )
        return image

    def _text(
        self,
        draw: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        size: int,
        fill: tuple[int, int, int] = _TEXT,
        max_width: int = _COLUMN_WIDTH,
    ) -> None:
        """Draw a text with a font that has its characters, cut to fit.

        Args:
            draw (ImageDraw.ImageDraw): Where to draw.
            xy (tuple[int, int]): Its top left corner.
            text (str): The text.
            size (int): The size in pixels.
            fill (tuple[int, int, int]): Its color.
            max_width (int): The room there is, in pixels.
        """
        font = self._fonts.font_for(text=text, size=size)
        draw.text(xy, shorten(text=text, font=font, max_width=max_width), font=font, fill=fill)

    def _draw_header(
        self, draw: ImageDraw.ImageDraw, stockpile: Stockpile, title: str, width: int
    ) -> None:
        """Draw the title and what locates the stockpile.

        Args:
            draw (ImageDraw.ImageDraw): Where to draw.
            stockpile (Stockpile): The stockpile.
            title (str): The title.
            width (int): The width of the image.
        """
        room = width - 2 * _MARGIN
        self._text(draw, xy=(_MARGIN, 14), text=title, size=_TITLE_SIZE, max_width=room)
        details = [
            self._labels.stockpile_type(stockpile.type),
            stockpile.hex or "",
            stockpile.shard or "",
        ]
        self._text(
            draw,
            xy=(_MARGIN, 54),
            text=" · ".join(detail for detail in details if detail),
            size=_SUBTITLE_SIZE,
            fill=_MUTED_TEXT,
            max_width=room,
        )

    def _draw_line(
        self, image: Image.Image, draw: ImageDraw.ImageDraw, line: ImageLine, x: int, y: int
    ) -> None:
        """Draw a heading or an item row.

        Args:
            image (Image.Image): The page, where the icons are pasted.
            draw (ImageDraw.ImageDraw): Where to draw.
            line (ImageLine): The line.
            x (int): Its left edge.
            y (int): Its top edge.
        """
        if line.is_heading:
            self._text(draw, xy=(x, y + 8), text=line.text, size=_HEADING_SIZE, fill=_HEADING_TEXT)
            return

        bottom = y + ROW_HEIGHT - _ROW_GAP
        draw.rectangle((x, y, x + _COLUMN_WIDTH, bottom), fill=_ROW_BACKGROUND)
        text_x = x + _TEXT_PADDING
        icon = self._icons.get((line.code or "", line.crated)) or self._icons.get(
            (line.code or "", False)
        )
        if icon is not None:
            image.paste(icon, (x + 2, y + 2))
            text_x = x + ICON_SIZE + _TEXT_PADDING

        quantity = line.quantity or ""
        quantity_font = self._fonts.font_for(text=quantity, size=_ROW_TEXT_SIZE)
        quantity_width = int(quantity_font.getlength(quantity))
        quantity_x = x + _COLUMN_WIDTH - _TEXT_PADDING - quantity_width
        draw.text((quantity_x, y + 8), quantity, font=quantity_font, fill=_TEXT)
        self._text(
            draw,
            xy=(text_x, y + 8),
            text=line.text,
            size=_ROW_TEXT_SIZE,
            max_width=quantity_x - text_x - _TEXT_PADDING,
        )

    def _draw_footer(
        self,
        draw: ImageDraw.ImageDraw,
        stockpile: Stockpile,
        page_label: str,
        width: int,
        height: int,
    ) -> None:
        """Draw the total, when the stockpile was read and which page this is.

        Args:
            draw (ImageDraw.ImageDraw): Where to draw.
            stockpile (Stockpile): The stockpile.
            page_label (str): Which page it is, empty if there is only one.
            width (int): The width of the image.
            height (int): The height of the image.
        """
        parts = [
            self._labels.total(total_quantity(stockpile)),
            stockpile.timestamp.strftime("%Y-%m-%d %H:%M"),
            page_label,
        ]
        self._text(
            draw,
            xy=(_MARGIN, height - _FOOTER_HEIGHT + 12),
            text=" · ".join(part for part in parts if part),
            size=_SUBTITLE_SIZE,
            fill=_MUTED_TEXT,
            max_width=width - 2 * _MARGIN,
        )
