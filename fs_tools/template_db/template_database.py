"""Template database for resolution-specific template storage and filtering."""

import logging
from typing import Any, cast

import h5py

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.icon_template import IconTemplate

logger = logging.getLogger(__name__)

# Database format version
# Version history:
#   1: Pickle format (monolithic or split files)
#   2: HDF5 format (groups per resolution with columnar storage)
DATABASE_VERSION = 2


class TemplateDatabase:
    """Resolution-specific template database with basic faction and mod filtering."""

    def __init__(self, resolution: SupportedResolution) -> None:
        """Initialize template database.

        Args:
            resolution (SupportedResolution): Target resolution for this database
        """
        self.resolution = resolution
        self.templates: list[IconTemplate] = []

        # Basic lookup tables for faction, mod, and category filtering (sets for fast intersection)
        self.faction_lookup: dict[str, set[int]] = {}
        self.mod_lookup: dict[str, set[int]] = {}
        self.category_lookup: dict[str, set[int]] = {}

    def add_template(self, template: IconTemplate) -> None:
        """Add template and update lookup tables.

        Args:
            template (IconTemplate): Template to add to database
        """
        idx = len(self.templates)
        self.templates.append(template)

        # Update faction lookup
        if template.faction.value not in self.faction_lookup:
            self.faction_lookup[template.faction.value] = set()
        self.faction_lookup[template.faction.value].add(idx)

        # Update mod lookup
        if template.mod not in self.mod_lookup:
            self.mod_lookup[template.mod] = set()
        self.mod_lookup[template.mod].add(idx)

        # Update category lookup
        if template.category.value not in self.category_lookup:
            self.category_lookup[template.category.value] = set()
        self.category_lookup[template.category.value].add(idx)

    @classmethod
    def load_from_hdf5_group(
        cls, group: h5py.Group, resolution: SupportedResolution
    ) -> "TemplateDatabase":
        """Load database from an HDF5 group.

        Args:
            group (h5py.Group): HDF5 group to load data from (e.g., /1080/)
            resolution (SupportedResolution): Resolution for this database

        Returns:
            TemplateDatabase: Loaded database with all templates

        Raises:
            ValueError: If group format is invalid or incompatible
        """
        logger.debug("Loading templates from HDF5 group %s", group.name)

        # Verify format
        if "version" not in group.attrs:
            raise ValueError(f"HDF5 group {group.name} missing version attribute")

        version = group.attrs["version"]
        if version != DATABASE_VERSION:
            raise ValueError(
                f"HDF5 group {group.name} has version {version}, expected {DATABASE_VERSION}. "
                f"Please regenerate your database using 'fs generate-templates'."
            )

        # Create database instance
        db = cls(resolution=resolution)

        # Load datasets
        n_templates = int(group.attrs["template_count"])  # type: ignore[arg-type]
        if n_templates == 0:
            logger.warning("HDF5 group %s has no templates", group.name)
            return db

        # h5py type hints are incomplete, cast to Any to avoid false positives
        group_any = cast(Any, group)

        images = group_any["images"][:]
        codes = group_any["codes"][:].astype(str)
        mods = group_any["mods"][:].astype(str)
        crated = group_any["crated"][:]
        faction_indices = group_any["faction"][:]
        category_indices = group_any["category"][:]
        phashes = group_any["phash"][:]

        # Convert indices back to enums
        faction_list = list(ItemFaction)
        category_list = list(ItemCategory)

        # Create IconTemplate objects
        for i in range(n_templates):
            template = IconTemplate(
                image=images[i],
                code=codes[i],
                crated=bool(crated[i]),
                resolution=resolution,
                faction=faction_list[faction_indices[i]],
                category=category_list[category_indices[i]],
                mod=mods[i],
            )
            # Set pre-computed optimization data
            template.phash = int(phashes[i])

            db.add_template(template)

        logger.debug("Loaded %d templates from HDF5 group %s", n_templates, group.name)
        return db

    def __len__(self) -> int:
        """Return number of templates in database."""
        return len(self.templates)

    def __repr__(self) -> str:
        """String representation of the database."""
        return (
            f"TemplateDatabase(resolution={self.resolution.value}, "
            f"templates={len(self.templates)}, "
            f"factions={len(self.faction_lookup)}, "
            f"mods={len(self.mod_lookup)})"
        )
