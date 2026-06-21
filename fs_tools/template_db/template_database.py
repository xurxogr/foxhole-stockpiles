"""Template database for resolution-specific template storage and filtering."""

import logging
import time
from typing import Any, cast

import h5py
import numpy as np

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.icon_template import IconTemplate

logger = logging.getLogger(__name__)

# Database format version
# Version history:
#   1: Pickle format (monolithic or split files)
#   2: HDF5 format (groups per resolution with columnar storage)
DATABASE_VERSION = 2
DATABASE_FORMAT = "hdf5"  # Current format: "hdf5"


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

        # Vectorized phash array for fast distance computation
        self._phash_array: np.ndarray | None = None

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

    def get_candidates(
        self,
        faction: ItemFaction | None = None,
        mod: str | None = None,
        category: ItemCategory | None = None,
        crated: bool | None = None,
        code: str | None = None,
        excluded_codes: list[str] | None = None,
    ) -> list[int]:
        """Get candidate template indices using faction, mod, category, and crated filters.

        Args:
            faction (ItemFaction | None): Optional faction filter
            mod (str | None): Optional mod filter
            category (ItemCategory | None): Optional category filter
            crated (bool | None): Optional crated filter (True for crated only,
                False for normal only, None for both)
            code (str | None): Optional item code filter
            excluded_codes (list[str] | None): Optional list of item codes to exclude from results

        Returns:
            list[int]: Candidate template indices for matching
        """
        candidates = set(range(len(self.templates)))

        if code:
            # Filter by item code if specified
            candidates = {i for i in candidates if code in self.templates[i].code}

        # Apply category filter if specified
        if category and category != ItemCategory.Invalid:
            category_candidates = self.category_lookup.get(category.value, set())
            candidates = candidates & category_candidates

        # Apply mod filter if specified
        if mod:
            mod_candidates = self.mod_lookup.get(mod, set())
            candidates = candidates & mod_candidates

        # Apply faction filter if specified
        if faction and faction != ItemFaction.NEUTRAL:
            faction_candidates = self.faction_lookup.get(faction.value, set())
            # Also include neutral items
            neutral_candidates = self.faction_lookup.get(ItemFaction.NEUTRAL.value, set())
            candidates = candidates & (faction_candidates | neutral_candidates)

        # Apply crated filter if specified
        if crated is not None:
            crated_candidates = []
            for idx in candidates:
                template = self.templates[idx]
                if template.crated == crated:
                    crated_candidates.append(idx)
            candidates = set(crated_candidates)

        # Apply excluded_codes filter if specified
        if excluded_codes:
            excluded_candidates = []
            for idx in candidates:
                template = self.templates[idx]
                if template.code not in excluded_codes:
                    excluded_candidates.append(idx)
            candidates = set(excluded_candidates)

        logger.debug(
            (
                "Candidate filtering: faction=%s, mod=%s, category=%s, crated=%s, "
                "candidates=%d, code=%s, excluded_codes=%s"
            ),
            faction.value if faction else "any",
            mod or "any",
            category.value if category else "any",
            crated if crated is not None else "any",
            len(candidates),
            code or "any",
            excluded_codes or "none",
        )

        return list(candidates)

    def get_available_mods(self) -> set[str]:
        """Get all mods available in this database.

        Returns:
            set[str]: Set of mod names present in the database
        """
        return set(self.mod_lookup.keys())

    def save_to_hdf5_group(self, group: h5py.Group) -> None:
        """Save database to an HDF5 group.

        Args:
            group (h5py.Group): HDF5 group to save data to (e.g., /1080/)
        """
        start_time = time.perf_counter()
        n_templates = len(self.templates)

        if n_templates == 0:
            logger.warning("No templates to save for resolution %s", self.resolution)
            # Still save metadata for empty database
            group.attrs["resolution"] = self.resolution.value
            group.attrs["template_count"] = 0
            group.attrs["icon_size"] = 0
            group.attrs["version"] = DATABASE_VERSION
            group.attrs["format"] = DATABASE_FORMAT
            return

        logger.debug("Saving %d templates to HDF5 group %s", n_templates, group.name)

        # Get image dimensions from first template (all same size for this resolution)
        first_image = self.templates[0].image
        img_h, img_w, img_c = first_image.shape

        # Create datasets with appropriate dtypes and compression
        # Images: (N, H, W, 3) uint8 with compression
        images_ds = group.create_dataset(
            "images",
            shape=(n_templates, img_h, img_w, img_c),
            dtype=np.uint8,
            compression="gzip",
            compression_opts=4,
        )

        # Metadata: variable-length strings for codes and mods
        str_dtype = h5py.string_dtype(encoding="utf-8")
        codes_ds = group.create_dataset("codes", shape=(n_templates,), dtype=str_dtype)
        mods_ds = group.create_dataset("mods", shape=(n_templates,), dtype=str_dtype)

        # Metadata: fixed-size types
        crated_ds = group.create_dataset("crated", shape=(n_templates,), dtype=bool)
        faction_ds = group.create_dataset("faction", shape=(n_templates,), dtype=np.uint8)
        category_ds = group.create_dataset("category", shape=(n_templates,), dtype=np.uint8)

        # Optimization data
        phash_ds = group.create_dataset("phash", shape=(n_templates,), dtype=np.uint64)

        # Fill datasets
        for i, template in enumerate(self.templates):
            images_ds[i] = template.image
            codes_ds[i] = template.code
            mods_ds[i] = template.mod
            crated_ds[i] = template.crated  # type: ignore[assignment]
            faction_ds[i] = list(ItemFaction).index(template.faction)  # type: ignore[assignment]
            category_ds[i] = list(ItemCategory).index(template.category)  # type: ignore[assignment]
            phash_ds[i] = template.phash  # type: ignore[assignment]

        # Store metadata as attributes
        group.attrs["resolution"] = self.resolution.value
        group.attrs["template_count"] = n_templates
        group.attrs["icon_size"] = img_h
        group.attrs["version"] = DATABASE_VERSION
        group.attrs["format"] = DATABASE_FORMAT

        elapsed = time.perf_counter() - start_time
        logger.info(
            "Saved %d templates (%dx%d) to HDF5 group %s in %.2f seconds",
            n_templates,
            img_h,
            img_w,
            group.name,
            elapsed,
        )

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

        # Store phash array for vectorized distance computation
        db._phash_array = phashes.astype(np.uint64)

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

    def get_phash_distances(
        self,
        icon_phash: int,
        candidate_indices: list[int],
    ) -> np.ndarray:
        """Compute hamming distances between icon phash and candidate templates.

        Uses vectorized NumPy operations for fast computation.

        Args:
            icon_phash (int): Perceptual hash of the icon to match.
            candidate_indices (list[int]): Indices of candidate templates to compare.

        Returns:
            np.ndarray: Array of hamming distances for each candidate.
        """
        if self._phash_array is None:
            # Fallback: build array from templates (shouldn't happen normally)
            self._phash_array = np.array([t.phash for t in self.templates], dtype=np.uint64)

        # Get phashes for candidates only
        candidate_phashes = self._phash_array[candidate_indices]

        # Vectorized XOR
        xor_result = np.bitwise_xor(candidate_phashes, np.uint64(icon_phash))

        # Vectorized popcount using unpackbits
        # Convert uint64 to bytes, unpack bits, sum
        xor_bytes = xor_result.view(np.uint8).reshape(-1, 8)
        bit_counts: np.ndarray = np.unpackbits(xor_bytes, axis=1).sum(axis=1)

        return bit_counts
