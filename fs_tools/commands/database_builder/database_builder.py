"""Database builder for creating resolution-specific template databases."""

import argparse
import asyncio
import logging
from copy import copy
from pathlib import Path

import cv2
import numpy

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.utils import load_catalog
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.catalog_item import CatalogItem
from foxhole_stockpiles.models.icon_template import IconTemplate
from fs_tools.template_db.template_database import TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager


class DatabaseBuilder:
    """Builds basic template databases from extracted game assets."""

    def __init__(self, catalog_path: Path, assets_path: Path, use_scaling: bool = False) -> None:
        """Initialize database builder.

        Args:
            catalog_path (Path): Path to catalog.json file
            assets_path (Path): Path to extracted assets directory
            use_scaling (bool): If True, scale from largest available size when exact size not found

        Raises:
            ValueError: If catalog is empty or cannot be loaded
        """
        self._logger = logging.getLogger(__name__)
        self.assets_path = assets_path
        self.icon_scaling_factor = 64 / 2160  # 64px at 2160p resolution
        self.use_scaling = use_scaling

        # Load catalog data directly
        self.catalog_data = load_catalog(path=catalog_path)
        if not self.catalog_data:
            raise ValueError(f"Catalog is empty or could not be loaded from {catalog_path}")

    async def build_all_databases(
        self,
        output_path: Path,
        target_resolutions: list[SupportedResolution] | None = None,
        overwrite: bool = True,
        workers: int | None = None,
    ) -> None:
        """Build template databases for specified or all supported resolutions.

        Args:
            output_path (Path): Output path for binary database file
            target_resolutions (list[SupportedResolution] | None): Specific resolutions to build,
                or None to build all supported resolutions
            overwrite (bool): If True, replace existing templates. If False, merge new templates
                into existing database (default: True)
            workers (int | None): Number of worker processes for database saving.
                Set to 1 to disable multiprocessing (recommended for GUI).
        """
        # Determine which resolutions to build
        resolutions_to_build = target_resolutions or list(SupportedResolution)

        self._logger.info(
            "Starting database build process for %d resolutions: %s (overwrite=%s)",
            len(resolutions_to_build),
            [str(r.value) for r in resolutions_to_build],
            overwrite,
        )

        # Build databases for specified resolutions
        databases: dict[SupportedResolution, TemplateDatabase] = {}
        for resolution in resolutions_to_build:
            self._logger.debug("Building database for resolution %s", resolution)
            database = await self._build_resolution_database(resolution=resolution)

            if len(database.templates) > 0:
                databases[resolution] = database
                self._logger.debug(
                    "Resolution %s: %d templates created", resolution, len(database.templates)
                )
            else:
                self._logger.warning("Resolution %s: NO templates found - skipping", resolution)

        if not databases:
            raise ValueError("No templates found for any resolution! Check your icon files.")

        # Merge with existing database (if it exists)
        has_changes = True  # Default to True for new database
        if output_path.exists():
            databases, has_changes = await self._merge_with_existing(
                new_databases=databases, output_path=output_path, overwrite=overwrite
            )

        # Save combined database only if there are changes
        if has_changes:
            await self._save_databases(
                databases=databases, output_path=output_path, workers=workers
            )
        else:
            self._logger.info("No new templates to add, skipping database save (no changes)")
        self._logger.debug("Database build completed successfully")

    async def _build_resolution_database(self, resolution: SupportedResolution) -> TemplateDatabase:
        """Build template database for specific resolution.

        Args:
            resolution (SupportedResolution): Target resolution

        Returns:
            TemplateDatabase: Built database with all templates
        """
        database = TemplateDatabase(resolution=resolution)
        resolution_height = int(resolution.value)

        # Calculate icon size for this resolution
        icon_size = int(self.icon_scaling_factor * resolution_height)

        self._logger.info(
            "Building templates for resolution %s (icon size: %dpx)", resolution, icon_size
        )

        # Process items in parallel
        semaphore = asyncio.Semaphore(8)  # Limit concurrent operations

        async def process_with_semaphore(item: CatalogItem) -> list[IconTemplate]:
            async with semaphore:
                return await self._process_item_templates(
                    item=item,
                    resolution=resolution,
                    icon_size=icon_size,
                )

        # Create tasks for all items
        tasks = [process_with_semaphore(item) for item in self.catalog_data]

        # Collect results
        results = await asyncio.gather(*tasks)
        for templates in results:
            for template in templates:
                database.add_template(template=template)

        self._logger.debug(
            "Built %d templates for resolution %s", len(database.templates), resolution
        )

        return database

    async def _process_item_templates(
        self, item: CatalogItem, resolution: SupportedResolution, icon_size: int
    ) -> list[IconTemplate]:
        """Process templates for a single item.

        Args:
            item (CatalogItem): Item definition from catalog
            resolution (SupportedResolution): Target resolution
            icon_size (int): Target icon size in pixels

        Returns:
            list[IconTemplate]: Generated templates for this item
        """
        templates: list[IconTemplate] = []
        item_code = item.code

        if not item_code:
            self._logger.warning("Item missing code: %s", item)
            return templates

        # Use faction from CatalogItem (already converted to ItemFaction)
        faction = item.faction

        # Find icon files for this item
        icon_paths = self._find_icon_files(item_code=item_code, icon_size=icon_size)

        for icon_path in icon_paths:
            # Load and process icon (cv2.imread is blocking, but fast enough for individual files)
            icon_image = await asyncio.to_thread(cv2.imread, str(icon_path))
            if icon_image is None:
                self._logger.warning("Failed to load icon: %s", icon_path)
                continue

            # Resize to target size
            icon_image = cv2.resize(icon_image, (icon_size, icon_size))

            # Determine if this is a crated variant
            is_crated = "crated" in icon_path.name.lower()

            # Extract mod name from filename (first part before underscore)
            filename_parts = icon_path.stem.split("_")
            mod_name = filename_parts[0] if filename_parts else "unknown"

            # Create template using Pydantic model
            try:
                template = IconTemplate(
                    image=icon_image.astype(numpy.uint8),
                    code=item_code,
                    crated=is_crated,
                    resolution=resolution,
                    faction=faction,
                    category=item.category,
                    mod=mod_name,
                )
                templates.append(template)
            except Exception as e:
                self._logger.error("Failed to create template for %s: %s", item_code, e)
                continue

        if not templates:
            self._logger.warning("No templates generated for item: %s", item_code)

        return templates

    def _find_icon_files(self, item_code: str, icon_size: int) -> list[Path]:
        """Find icon files for item and target icon size.

        Args:
            item_code (str): Item code name
            icon_size (int): Target icon size in pixels

        Returns:
            list[Path]: Paths to icon files with exact or scalable sizes
        """
        icon_paths: list[Path] = []

        self._logger.debug(
            "Looking for size %d for item %s (scaling=%s)",
            icon_size,
            item_code,
            self.use_scaling,
        )

        # Look for normal (non-crated) item folder
        item_folder = self.assets_path / item_code
        if item_folder.exists():
            icon_paths.extend(
                self._find_size_variants(
                    folder=item_folder,
                    item_code=item_code,
                    target_size=icon_size,
                    is_crated=False,
                )
            )

        # Look for crated variant folder
        crated_folder = self.assets_path / f"{item_code}_crated"
        if crated_folder.exists():
            icon_paths.extend(
                self._find_size_variants(
                    folder=crated_folder,
                    item_code=item_code,
                    target_size=icon_size,
                    is_crated=True,
                )
            )

        if not icon_paths:
            level = logging.DEBUG if self.use_scaling else logging.WARNING
            self._logger.log(level, "No icons found for item %s at size %d", item_code, icon_size)

        return icon_paths

    def _find_size_variants(
        self, folder: Path, item_code: str, target_size: int, is_crated: bool
    ) -> list[Path]:
        """Find size variants in a folder with exact match or scaling fallback.

        Args:
            folder (Path): Folder to search in
            item_code (str): Item code name
            target_size (int): Target icon size
            is_crated (bool): Whether this is a crated variant

        Returns:
            list[Path]: Found icon file paths
        """
        found_paths: list[Path] = []
        crated_suffix = "_crated" if is_crated else ""

        # First try: exact size match
        exact_pattern = f"*_{item_code}{crated_suffix}_{target_size}.png"
        exact_files = list(folder.glob(exact_pattern))

        if exact_files:
            found_paths.extend(exact_files)
            self._logger.debug(
                "Found %d EXACT size (%d) variants for %s%s",
                len(exact_files),
                target_size,
                item_code,
                crated_suffix,
            )
            return found_paths

        # Second try: scaling fallback (if enabled)
        if not self.use_scaling:
            self._logger.debug(
                "Exact size %d not found for %s%s, scaling disabled",
                target_size,
                item_code,
                crated_suffix,
            )
            return found_paths
        all_pattern = f"*_{item_code}{crated_suffix}_*.png"
        all_files = list(folder.glob(all_pattern))

        if not all_files:
            self._logger.debug("No files found matching pattern %s in %s", all_pattern, folder)
            return found_paths

        # Group by mod name and find largest size for each mod
        mod_files: dict[str, tuple[Path, int]] = {}
        for file_path in all_files:
            # Extract mod name and size
            parts = file_path.stem.split("_")
            if len(parts) >= 3:
                mod_name = parts[0]
                try:
                    size = int(parts[-1])
                    if mod_name not in mod_files or size > mod_files[mod_name][1]:
                        mod_files[mod_name] = (file_path, size)
                except ValueError:
                    self._logger.warning("Invalid size in filename: %s", file_path.name)
                    continue

        # Use largest available size for each mod (will be scaled during template creation)
        for file_path, source_size in mod_files.values():
            found_paths.append(file_path)
            self._logger.debug(
                "Will SCALE %s%s from size %d to %d",
                item_code,
                crated_suffix,
                source_size,
                target_size,
            )

        return found_paths

    async def _merge_with_existing(
        self,
        new_databases: dict[SupportedResolution, TemplateDatabase],
        output_path: Path,
        overwrite: bool = False,
    ) -> tuple[dict[SupportedResolution, TemplateDatabase], bool]:
        """Merge new databases with existing database file.

        Args:
            new_databases (dict[SupportedResolution, TemplateDatabase]): Newly built databases
            output_path (Path): Path to existing database file
            overwrite (bool): If True, replace matching templates. If False, skip duplicates.

        Returns:
            tuple: (merged_databases, has_changes) - Merged databases and whether changes were made
        """
        # If database doesn't exist, just return new databases (always has changes)
        if not output_path.exists():
            self._logger.info("No existing database at %s, using new databases", output_path)
            return new_databases, True

        self._logger.info(
            "Merging with existing database: %s (overwrite=%s)", output_path, overwrite
        )

        # Load existing databases
        temp_manager = TemplateManager(database_path=output_path)
        existing_databases = await temp_manager.load_all_resolutions()

        merged_databases: dict[SupportedResolution, TemplateDatabase] = {}
        stats = {
            "resolutions": 0,
            "new_templates": 0,
            "existing_templates": 0,
            "skipped": 0,
            "replaced": 0,
        }

        # Build set of new template keys for quick lookup when overwriting
        # Key format: (code, crated, mod)
        new_keys_by_resolution: dict[SupportedResolution, set[tuple[str, bool, str]]] = {}
        for resolution, new_db in new_databases.items():
            new_keys_by_resolution[resolution] = {
                (t.code, t.crated, t.mod) for t in new_db.templates
            }

        # Merge each resolution
        for resolution in set(list(existing_databases.keys()) + list(new_databases.keys())):
            existing_db: TemplateDatabase | None = existing_databases.get(resolution)
            new_db_for_res: TemplateDatabase | None = new_databases.get(resolution)

            if new_db_for_res is None:
                # No new templates for this resolution, keep existing
                if existing_db:
                    merged_databases[resolution] = existing_db
                    stats["existing_templates"] += len(existing_db.templates)
                continue

            if existing_db is None:
                # No existing templates for this resolution, use new
                merged_databases[resolution] = new_db_for_res
                stats["new_templates"] += len(new_db_for_res.templates)
                stats["resolutions"] += 1
                continue

            # Both exist, merge them
            self._logger.debug(
                "Merging resolution %s: existing=%d, new=%d",
                resolution,
                len(existing_db.templates),
                len(new_db_for_res.templates),
            )

            merged_db = TemplateDatabase(resolution=resolution)
            new_keys = new_keys_by_resolution.get(resolution, set())

            # Add existing templates (skip those being replaced if overwrite=True)
            for template in existing_db.templates:
                key = (template.code, template.crated, template.mod)
                if overwrite and key in new_keys:
                    # Skip this template - it will be replaced by the new one
                    stats["replaced"] += 1
                    self._logger.debug(
                        "Replacing template: %s (crated=%s, mod=%s)",
                        template.code,
                        template.crated,
                        template.mod,
                    )
                else:
                    merged_db.add_template(template)
                    stats["existing_templates"] += 1

            # Create set of keys now in merged_db for duplicate detection
            merged_keys = {(t.code, t.crated, t.mod) for t in merged_db.templates}

            # Add new templates
            for template in new_db_for_res.templates:
                key = (template.code, template.crated, template.mod)
                if key in merged_keys:
                    # Duplicate (only happens when overwrite=False)
                    self._logger.debug(
                        "Skipping duplicate template: %s (crated=%s, mod=%s)",
                        template.code,
                        template.crated,
                        template.mod,
                    )
                    stats["skipped"] += 1
                else:
                    self._logger.debug(
                        "Adding new template: %s (crated=%s, mod=%s)",
                        template.code,
                        template.crated,
                        template.mod,
                    )
                    merged_db.add_template(template)
                    stats["new_templates"] += 1
                    merged_keys.add(key)

            merged_databases[resolution] = merged_db

        self._logger.info(
            "Merge complete: %d resolutions, %d new templates added, "
            "%d existing templates preserved, %d duplicates skipped, %d replaced",
            len(merged_databases),
            stats["new_templates"],
            stats["existing_templates"],
            stats["skipped"],
            stats["replaced"],
        )

        # Return databases and whether any changes were made
        has_changes = stats["new_templates"] > 0 or stats["replaced"] > 0
        return merged_databases, has_changes

    async def _save_databases(
        self,
        databases: dict[SupportedResolution, TemplateDatabase],
        output_path: Path,
        workers: int | None = None,
    ) -> None:
        """Save all databases to HDF5 file.

        Args:
            databases (dict[SupportedResolution, TemplateDatabase]): Built databases
            output_path (Path): Output file path
            workers (int | None): Number of worker processes. Set to 1 to disable multiprocessing.
        """
        self._logger.debug("Saving databases to HDF5 file: %s", output_path)

        # Save using centralized method
        await asyncio.to_thread(
            TemplateManager.save_databases_to_hdf5, databases, output_path, workers
        )

        # Log statistics
        total_templates = sum(len(db.templates) for db in databases.values())
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB

        self._logger.info(
            "Database saved: %d resolutions, %d total templates, %.1f MB",
            len(databases),
            total_templates,
            file_size,
        )


async def main() -> None:
    """Main entry point for database builder."""
    parser = argparse.ArgumentParser(description="Build template databases")
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Path to catalog.json (default: from database_builder.catalog_file setting)",
    )
    parser.add_argument("--templates", type=Path, required=True, help="Path to extracted templates")
    parser.add_argument(
        "--database",
        type=Path,
        help="Output database path (default: from scanner.database_path setting)",
    )
    parser.add_argument(
        "--use-scaling",
        action="store_true",
        help="Scale from largest available size when exact size not found (better quality)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging (debug level)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress all output except errors and warnings. "
        "Only errors will be printed to console.",
    )
    parser.add_argument("--log-file", type=Path, help="Path to log file (default: console only)")
    parser.add_argument(
        "--resolution",
        action="append",
        help=(
            "Resolution to generate (can be specified multiple times, e.g., --resolution 1024"
            " --resolution 2160). If not specified, uses database_builder.target_resolutions"
            " setting or all supported resolutions if not configured."
        ),
    )

    args = parser.parse_args()

    # Setup logging
    settings = get_settings()

    # Use catalog from args or fall back to config
    catalog_path = (
        args.catalog if args.catalog is not None else settings.database_builder.catalog_file
    )
    if catalog_path is None:
        parser.error(
            "Catalog path must be provided via --catalog or database_builder.catalog_file setting"
        )

    # Use database from args or fall back to config
    database_path = args.database if args.database is not None else settings.scanner.database_path
    if database_path is None:
        parser.error(
            "Database path must be provided via --database or scanner.database_path setting"
        )

    # Parse and validate resolutions if specified, otherwise use settings
    target_resolutions: list[SupportedResolution] | None = None
    if args.resolution:
        # User specified resolutions via CLI
        target_resolutions = []
        for res_str in args.resolution:
            try:
                resolution = SupportedResolution(res_str)
                target_resolutions.append(resolution)
            except ValueError:
                valid_resolutions = [r.value for r in SupportedResolution]
                parser.error(
                    f"Invalid resolution '{res_str}'. "
                    f"Valid resolutions are: {', '.join(valid_resolutions)}"
                )
    elif settings.database_builder.target_resolutions:
        # Use resolutions from settings (string list to enum list)
        target_resolutions = []
        for res_str in settings.database_builder.target_resolutions:
            try:
                resolution = SupportedResolution(res_str)
                target_resolutions.append(resolution)
            except ValueError:
                logging.warning("Invalid resolution in settings: '%s', skipping", res_str)
    # If still None, build_all_databases will use all supported resolutions

    logging_settings = copy(settings.logging)
    # Setup logging
    if args.quiet:
        logging_settings.log_level = "WARNING"
    elif args.verbose:
        logging_settings.log_level = "DEBUG"

    logging_settings.log_file = args.log_file
    setup_logging(logging_settings)

    # Build database
    builder = DatabaseBuilder(
        catalog_path=catalog_path, assets_path=args.templates, use_scaling=args.use_scaling
    )
    await builder.build_all_databases(
        output_path=database_path, target_resolutions=target_resolutions
    )
