"""Icon manager service for managing icons in template databases."""

import asyncio
import logging
from pathlib import Path

import numpy

from foxhole_stockpiles.core.image_io import read_bgr
from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.icon_template import IconTemplate
from fs_tools.template_db.template_database import TemplateDatabase


class IconManager:
    """Manages icons in template databases (add, replace, delete)."""

    def __init__(
        self,
        database_path: Path,
        databases: dict[SupportedResolution, TemplateDatabase],
        icon_scale: float,
    ) -> None:
        """Initialize icon manager with pre-loaded databases.

        Args:
            database_path (Path): Path to database file (for saving)
            databases (dict[SupportedResolution, TemplateDatabase]): Pre-loaded databases
            icon_scale (float): Icon scaling factor (ICON_BOX_SCALE)

        Raises:
            ValueError: If databases dict is empty
        """
        self._logger = logging.getLogger(__name__)
        self.database_path = database_path
        self.databases = databases
        self.icon_scale = icon_scale

        if not self.databases:
            raise ValueError("Databases dictionary cannot be empty")

    def _calculate_icon_size(self, resolution_height: int) -> int:
        """Calculate icon size for a given resolution.

        Args:
            resolution_height (int): Vertical resolution in pixels

        Returns:
            int: Icon size in pixels for the given resolution
        """
        return int(self.icon_scale * resolution_height)

    async def add_icon(
        self,
        icon_path: Path,
        item_code: str,
        faction: ItemFaction,
        category: ItemCategory,
        crated: bool,
        mod: str,
        resolution: SupportedResolution,
        replace: bool = False,
    ) -> None:
        """Add a single icon to the database for a specific resolution.

        Args:
            icon_path (Path): Path to icon image file
            item_code (str): Item code name
            faction (ItemFaction): Item faction
            category (ItemCategory): Item category
            crated (bool): Whether this is a crated variant
            mod (str): Mod name
            resolution (SupportedResolution): Target resolution
            replace (bool): If True, replace existing icon with same metadata; if False, error
                on duplicate

        Raises:
            FileNotFoundError: If icon file does not exist
            ValueError: If resolution not found in database, icon cannot be loaded,
                        or duplicate exists without replace flag
        """
        if not icon_path.exists():
            raise FileNotFoundError(f"Icon file not found: {icon_path}")

        if resolution not in self.databases:
            raise ValueError(
                f"Resolution {resolution.value} not found in database. "
                f"Available resolutions: {[r.value for r in self.databases.keys()]}"
            )

        # Load icon image
        self._logger.debug("Loading icon from %s", icon_path)
        icon_image = await asyncio.to_thread(read_bgr, str(icon_path))
        if icon_image is None:
            raise ValueError(f"Failed to load icon image: {icon_path}")

        # Calculate expected icon size for this resolution
        expected_size = self._calculate_icon_size(int(resolution.value))

        # Validate icon dimensions
        if icon_image.shape[0] != expected_size or icon_image.shape[1] != expected_size:
            raise ValueError(
                f"Icon has incorrect dimensions {icon_image.shape[1]}x{icon_image.shape[0]}. "
                f"Expected {expected_size}x{expected_size} for resolution {resolution.value}. "
                f"Please resize the icon before adding it to the database."
            )

        # Check for existing icon with same metadata
        database = self.databases[resolution]
        existing_idx = self._find_existing_icon(
            database=database,
            item_code=item_code,
            faction=faction,
            category=category,
            crated=crated,
            mod=mod,
        )

        # Create template
        template = IconTemplate(
            image=icon_image.astype(numpy.uint8),
            code=item_code,
            crated=crated,
            resolution=resolution,
            faction=faction,
            category=category,
            mod=mod,
        )

        if existing_idx is not None:
            if not replace:
                raise ValueError(
                    f"Icon already exists for '{item_code}' "
                    f"(faction={faction.value}, category={category.value}, "
                    f"crated={crated}, mod={mod}) in resolution {resolution.value}. "
                    f"Use --replace flag to replace existing icon."
                )
            # Replace in-place to preserve position
            self._logger.debug(
                "Replacing existing icon at index %d for '%s'", existing_idx, item_code
            )
            database.templates[existing_idx] = template
        else:
            # Add to database
            database.add_template(template=template)

        action = "Replaced" if existing_idx is not None else "Added"
        self._logger.info(
            "%s icon for '%s' to resolution %s (crated=%s, faction=%s, category=%s, mod=%s)",
            action,
            item_code,
            resolution.value,
            crated,
            faction.value,
            category.value,
            mod,
        )

    def add_icon_from_image(
        self,
        icon_image: numpy.ndarray,
        item_code: str,
        faction: ItemFaction,
        category: ItemCategory,
        crated: bool,
        mod: str,
        resolution: SupportedResolution,
        replace: bool = False,
    ) -> None:
        """Add an icon from an image array to the database (synchronous).

        This is useful when the image is already loaded (e.g., in GUI applications).

        Args:
            icon_image (numpy.ndarray): Icon image as BGR numpy array
            item_code (str): Item code name
            faction (ItemFaction): Item faction
            category (ItemCategory): Item category
            crated (bool): Whether this is a crated variant
            mod (str): Mod name
            resolution (SupportedResolution): Target resolution
            replace (bool): If True, replace existing icon with same metadata; if False, error
                on duplicate

        Raises:
            ValueError: If resolution not found in database, image is invalid,
                        or duplicate exists without replace flag
        """
        if resolution not in self.databases:
            raise ValueError(
                f"Resolution {resolution.value} not found in database. "
                f"Available resolutions: {[r.value for r in self.databases.keys()]}"
            )

        # Calculate expected icon size for this resolution
        expected_size = self._calculate_icon_size(int(resolution.value))

        # Validate icon dimensions
        if icon_image.shape[0] != expected_size or icon_image.shape[1] != expected_size:
            raise ValueError(
                f"Icon has incorrect dimensions {icon_image.shape[1]}x{icon_image.shape[0]}. "
                f"Expected {expected_size}x{expected_size} for resolution {resolution.value}. "
                f"Please resize the icon before adding it to the database."
            )

        # Check for existing icon with same metadata
        database = self.databases[resolution]
        existing_idx = self._find_existing_icon(
            database=database,
            item_code=item_code,
            faction=faction,
            category=category,
            crated=crated,
            mod=mod,
        )

        # Create template
        template = IconTemplate(
            image=icon_image.astype(numpy.uint8),
            code=item_code,
            crated=crated,
            resolution=resolution,
            faction=faction,
            category=category,
            mod=mod,
        )

        if existing_idx is not None:
            if not replace:
                raise ValueError(
                    f"Icon already exists for '{item_code}' "
                    f"(faction={faction.value}, category={category.value}, "
                    f"crated={crated}, mod={mod}) in resolution {resolution.value}. "
                    f"Use --replace flag to replace existing icon."
                )
            # Replace in-place to preserve position
            self._logger.debug(
                "Replacing existing icon at index %d for '%s'", existing_idx, item_code
            )
            database.templates[existing_idx] = template
        else:
            # Add to database
            database.add_template(template=template)

        action = "Replaced" if existing_idx is not None else "Added"
        self._logger.info(
            "%s icon for '%s' to resolution %s (crated=%s, faction=%s, category=%s, mod=%s)",
            action,
            item_code,
            resolution.value,
            crated,
            faction.value,
            category.value,
            mod,
        )

    def delete_icon(
        self,
        item_code: str,
        faction: ItemFaction,
        category: ItemCategory,
        crated: bool,
        mod: str,
        resolution: SupportedResolution,
    ) -> None:
        """Delete an icon from the database for a specific resolution.

        Args:
            item_code (str): Item code name
            faction (ItemFaction): Item faction
            category (ItemCategory): Item category
            crated (bool): Whether this is a crated variant
            mod (str): Mod name
            resolution (SupportedResolution): Target resolution

        Raises:
            ValueError: If resolution not found in database or icon not found
        """
        if resolution not in self.databases:
            raise ValueError(
                f"Resolution {resolution.value} not found in database. "
                f"Available resolutions: {[r.value for r in self.databases.keys()]}"
            )

        database = self.databases[resolution]
        existing_idx = self._find_existing_icon(
            database=database,
            item_code=item_code,
            faction=faction,
            category=category,
            crated=crated,
            mod=mod,
        )

        if existing_idx is None:
            raise ValueError(
                f"Icon not found for '{item_code}' "
                f"(faction={faction.value}, category={category.value}, "
                f"crated={crated}, mod={mod}) in resolution {resolution.value}."
            )

        # Remove the template
        database.templates.pop(existing_idx)
        self._rebuild_lookup_tables(database)

        self._logger.info(
            "Deleted icon for '%s' from resolution %s (crated=%s, faction=%s, category=%s, mod=%s)",
            item_code,
            resolution.value,
            crated,
            faction.value,
            category.value,
            mod,
        )

    def _find_existing_icon(
        self,
        database: TemplateDatabase,
        item_code: str,
        faction: ItemFaction,
        category: ItemCategory,
        crated: bool,
        mod: str,
    ) -> int | None:
        """Find existing icon with matching metadata.

        Args:
            database (TemplateDatabase): Database to search
            item_code (str): Item code name
            faction (ItemFaction): Item faction
            category (ItemCategory): Item category
            crated (bool): Whether this is a crated variant
            mod (str): Mod name

        Returns:
            int | None: Index of existing template, or None if not found
        """
        for idx, template in enumerate(database.templates):
            if (
                template.code == item_code
                and template.faction == faction
                and template.category == category
                and template.crated == crated
                and template.mod == mod
            ):
                return idx
        return None

    def _rebuild_lookup_tables(self, database: TemplateDatabase) -> None:
        """Rebuild database lookup tables after template removal.

        Args:
            database (TemplateDatabase): Database to rebuild
        """
        # Clear existing lookups
        database.faction_lookup.clear()
        database.mod_lookup.clear()
        database.category_lookup.clear()

        # Rebuild from templates
        for idx, template in enumerate(database.templates):
            # Update faction lookup
            if template.faction.value not in database.faction_lookup:
                database.faction_lookup[template.faction.value] = set()
            database.faction_lookup[template.faction.value].add(idx)

            # Update mod lookup
            if template.mod not in database.mod_lookup:
                database.mod_lookup[template.mod] = set()
            database.mod_lookup[template.mod].add(idx)

            # Update category lookup
            if template.category.value not in database.category_lookup:
                database.category_lookup[template.category.value] = set()
            database.category_lookup[template.category.value].add(idx)
