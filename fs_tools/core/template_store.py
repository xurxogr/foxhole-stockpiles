"""Read and edit the icon-template database through fs-assets."""

from pathlib import Path

import fs_assets
import numpy as np
from fs_assets.types import Faction, Template

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.database_statistics import DatabaseStatistics
from fs_tools.models.icon_template import IconTemplate

# Faction names as fs-assets takes them.
_FACTION_NAMES: dict[ItemFaction, Faction] = {
    ItemFaction.NEUTRAL: "neutral",
    ItemFaction.COLONIALS: "colonials",
    ItemFaction.WARDENS: "wardens",
}


def _to_icon_template(template: Template, resolution: SupportedResolution) -> IconTemplate:
    """Convert one fs-assets template record into an IconTemplate.

    Args:
        template (Template): The record returned by ``fs_assets.read_templates``.
        resolution (SupportedResolution): The resolution it was read from.

    Returns:
        IconTemplate: The template with its BGR image as a numpy array.
    """
    size = template["size"]
    image = np.frombuffer(template["image"], dtype=np.uint8).reshape(size, size, 3).copy()
    return IconTemplate(
        image=image,
        code=template["code"],
        crated=template["crated"],
        category=ItemCategory(template["category"]),
        faction=ItemFaction.from_string(template["faction"]),
        mod=template["mod_name"],
        resolution=resolution,
        phash=template["phash"],
    )


def read_resolution(database_path: Path, resolution: SupportedResolution) -> list[IconTemplate]:
    """Read the templates stored for one resolution.

    Args:
        database_path (Path): The template database.
        resolution (SupportedResolution): The resolution to read.

    Returns:
        list[IconTemplate]: The templates, in storage order.
    """
    records = fs_assets.read_templates(str(database_path), int(resolution.value))
    return [_to_icon_template(record, resolution) for record in records]


def read_statistics(database_path: Path) -> DatabaseStatistics:
    """Count the templates per mod and resolution.

    Args:
        database_path (Path): The template database.

    Returns:
        DatabaseStatistics: The resolutions holding templates (ascending) and the
            template count per mod and resolution.
    """
    stats = fs_assets.database_statistics(str(database_path))
    mod_stats = {
        mod: {str(resolution): count for resolution, count in counts.items()}
        for mod, counts in stats["mods"].items()
    }
    used = {resolution for counts in mod_stats.values() for resolution in counts}
    resolutions = [str(res) for res in stats["resolutions"] if str(res) in used]
    return DatabaseStatistics(resolutions=resolutions, mod_stats=mod_stats)


def read_all_resolutions(database_path: Path) -> dict[SupportedResolution, list[IconTemplate]]:
    """Read the templates of every resolution that holds any.

    Args:
        database_path (Path): The template database.

    Returns:
        dict[SupportedResolution, list[IconTemplate]]: Templates per resolution.
    """
    return {
        SupportedResolution(resolution): read_resolution(
            database_path, SupportedResolution(resolution)
        )
        for resolution in read_statistics(database_path).resolutions
    }


def replace_icon(database_path: Path, template: IconTemplate, icon_path: Path) -> None:
    """Replace one template's image at its resolution with a new icon.

    The icon (a PNG or a game ``.uasset``) is resized and composited exactly
    like templates built from the game files.

    Args:
        database_path (Path): The template database.
        template (IconTemplate): The template to replace.
        icon_path (Path): The new icon image.
    """
    fs_assets.modify_icon(
        str(database_path),
        code=template.code,
        faction=_FACTION_NAMES[template.faction],
        category=template.category.value,
        crated=template.crated,
        mod_name=template.mod,
        resolution=[int(template.resolution.value)],
        icon=str(icon_path),
        replace=True,
    )


def delete_icon(database_path: Path, template: IconTemplate) -> None:
    """Delete one template at its resolution.

    Args:
        database_path (Path): The template database.
        template (IconTemplate): The template to delete.
    """
    fs_assets.modify_icon(
        str(database_path),
        code=template.code,
        faction=_FACTION_NAMES[template.faction],
        category=template.category.value,
        crated=template.crated,
        mod_name=template.mod,
        resolution=[int(template.resolution.value)],
        remove=True,
    )
