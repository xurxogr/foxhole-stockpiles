"""Draw a stockpile as the settings of a handler say."""

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.catalog_service import get_catalog_service
from foxhole_stockpiles.services.stockpile_image.font_selector import FontSelector
from foxhole_stockpiles.services.stockpile_image.icons import load_icons
from foxhole_stockpiles.services.stockpile_image.image_text import ImageText
from foxhole_stockpiles.services.stockpile_image.placeholders import fill_template
from foxhole_stockpiles.services.stockpile_image.renderer import StockpileImageRenderer


def fill_stockpile_text(
    settings: StockpileImageSettings, template: str | None, stockpile: Stockpile
) -> str | None:
    """Fill a text the user wrote, in the language of the output.

    Args:
        settings (StockpileImageSettings): How to draw the stockpile.
        template (str | None): The text, with placeholders.
        stockpile (Stockpile): The stockpile.

    Returns:
        str | None: The text with its values, or None if it is blank.
    """
    text = (template or "").strip()
    if not text:
        return None
    labels = ImageText(catalog=get_catalog_service(), language=settings.language)
    return fill_template(
        template=text, stockpile=stockpile, type_label=labels.stockpile_type(stockpile.type)
    )


def render_stockpile(settings: StockpileImageSettings, stockpile: Stockpile) -> list[bytes]:
    """Draw a stockpile.

    Args:
        settings (StockpileImageSettings): How to draw it.
        stockpile (Stockpile): The stockpile.

    Returns:
        list[bytes]: The PNG of each page.
    """
    renderer = StockpileImageRenderer(
        text=ImageText(catalog=get_catalog_service(), language=settings.language),
        font_selector=FontSelector(font_path=settings.font_path),
        icons=load_icons(database_path=get_settings().scanner.database_path, mod=settings.icon_mod),
    )
    return renderer.render_png(stockpile)
