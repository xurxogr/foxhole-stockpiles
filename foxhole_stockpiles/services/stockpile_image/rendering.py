"""Draw a stockpile as the settings of a handler say."""

from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.sections.output.stockpile_image_settings import (
    StockpileImageSettings,
)
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.catalog_service import get_catalog_service
from foxhole_stockpiles.services.stockpile_image.font_selector import FontSelector
from foxhole_stockpiles.services.stockpile_image.icons import load_icons
from foxhole_stockpiles.services.stockpile_image.placeholders import fill_template
from foxhole_stockpiles.services.stockpile_image.renderer import StockpileImageRenderer


def render_stockpile(settings: StockpileImageSettings, stockpile: Stockpile) -> list[bytes]:
    """Draw a stockpile.

    Args:
        settings (StockpileImageSettings): How to draw it.
        stockpile (Stockpile): The stockpile.

    Returns:
        list[bytes]: The PNG of each page.
    """
    renderer = StockpileImageRenderer(
        catalog=get_catalog_service(),
        font_selector=FontSelector(font_path=settings.font_path),
        icons=load_icons(database_path=get_settings().scanner.database_path, mod=settings.icon_mod),
    )
    headline = (settings.headline or "").strip()
    return renderer.render_png(
        stockpile=stockpile,
        headline=fill_template(template=headline, stockpile=stockpile) if headline else None,
    )
