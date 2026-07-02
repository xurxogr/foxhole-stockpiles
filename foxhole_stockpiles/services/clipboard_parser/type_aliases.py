"""Localized stockpile-type display names -> runtime ``StockpileType``."""

from __future__ import annotations

import logging

from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.services.clipboard_parser.code_map import _normalize

logger = logging.getLogger(__name__)

# Stockpile type display names (in any game language) -> runtime type. Type
# names do not collide across languages, so a single flat map is
# language-agnostic. Unknown types fall back to UNDEFINED.
_TYPE_ALIASES: list[tuple[StockpileType, tuple[str, ...]]] = [
    (StockpileType.SEAPORT, ("Seaport", "Seehafen", "Port", "Porto", "Морской порт", "海港")),
    (
        StockpileType.STORAGE_DEPOT,
        ("Storage Depot", "Lagerdepot", "Dépôt", "Depósito", "Складское помещение", "仓库"),
    ),
    (StockpileType.AIRCRAFT_DEPOT, ("Aircraft Depot",)),
    (
        StockpileType.ENCAMPMENT,
        ("Encampment", "Feldlager", "Campement", "Acampamento", "Лагерь", "营地"),
    ),
    (StockpileType.KEEP, ("Keep", "Wehrturm", "Place Forte", "Torreão", "Крепость", "要塞")),
    (
        StockpileType.SAFE_HOUSE,
        ("Safe House", "Unterschlupf", "Planque", "Casa Fortificada", "Убежище", "安全屋"),
    ),
    (
        StockpileType.RELIC_BASE,
        (
            "Relic Base",
            "Reliktbasis",
            "Base Relique",
            "Base Relíquia",
            "Реликтовая База",
            "遗迹基地",
        ),
    ),
    (
        StockpileType.BUNKER_BASE_1,
        (
            "Bunker Base",
            "Bunkerbasis",
            "Base Bunker",
            "Centro do Bunker",
            "Бункерная база",
            "地堡基地",
        ),
    ),
    (
        StockpileType.BORDER_BASE,
        (
            "Border Base",
            "Grenzbasis",
            "Base Frontalière",
            "Base Fronteiriça",
            "Пограничная База",
            "边境基地",
        ),
    ),
    (
        StockpileType.TOWN_BASE_1,
        (
            "Town Base",
            "Town Hall",
            "Stadtkernbasis",
            "Quartier Général",
            "Base da Cidade",
            "Ратуша",
            "城镇基地",
        ),
    ),
    (
        StockpileType.UNDERGROUND_FORTRESS,
        (
            "Underground Fortress",
            "Untergrundfestung",
            "Forteresse Souterraine",
            "Bunker Subterrâneo",
            "Подземная Крепость",
            "地下要塞",
        ),
    ),
]
_TYPE_BY_DISPLAY: dict[str, StockpileType] = {
    name.lower(): stockpile_type for stockpile_type, names in _TYPE_ALIASES for name in names
}


def _type_from_display(display: str) -> str:
    """Map an exported stockpile type display name (any language) to a type.

    Known display names normalize to their canonical type; an unrecognized one
    (e.g. a type added before the alias table is updated) keeps its display name
    rather than collapsing to "Undefined".

    Args:
        display (str): The type field from the header (e.g. "Seaport").

    Returns:
        str: The matching canonical type, or the raw display name when unknown.
    """
    stockpile_type = _TYPE_BY_DISPLAY.get(_normalize(display).lower())
    if stockpile_type is None:
        logger.debug("Unknown stockpile type in clipboard header: %r", display)
        return display
    return stockpile_type
