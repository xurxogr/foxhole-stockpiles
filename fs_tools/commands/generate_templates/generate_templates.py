"""Generate training templates command for Foxhole stockpile recognition system."""

import argparse
import asyncio
import logging
from copy import copy
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from PIL.Image import Resampling

from foxhole_stockpiles.core.image_io import write_bgr
from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.catalog_item import CatalogItem
from fs_tools.core.settings.sections.templates import TemplateSettings
from fs_tools.core.utils import load_catalog

logger = logging.getLogger(__name__)


class TemplateGenerator:
    """Generate icon templates from extracted game assets.

    Creates normal and crated versions of icons for multiple resolutions, handles subicon overlays,
    and organizes output by CodeName.
    """

    ICON_SIZE_RATIO: float = 64 / 2160
    SUBICON_ASPECT_RATIO: float = 7 / 16
    SUBICON_ALPHA: float = 0.75
    VANILLA_MOD_NAME: str = "vanilla"
    # Minimum percentage of non-transparent pixels for a subicon to be considered valid
    BLANK_SUBICON_THRESHOLD: float = 0.05

    def __init__(
        self,
        catalog_path: Path,
        assets_path: Path,
        template_path: Path,
        filter_name: str | None = None,
        template_settings: TemplateSettings | None = None,
    ) -> None:
        """Initialize the template generator.

        Args:
            catalog_path (Path): Path to the catalog.json configuration file
            assets_path (Path): Path to extracted assets directory with mod subfolders
            template_path (Path): Path where generated templates will be saved
            filter_name (str | None): Optional filter to process only items containing this string
            template_settings (TemplateSettings | None): Template generation settings
        """
        if not catalog_path.exists():
            raise FileNotFoundError(f"Catalog file not found: {catalog_path}")
        if not assets_path.exists():
            raise FileNotFoundError(f"Assets directory not found: {assets_path}")

        self.assets_path = assets_path
        self.template_path = template_path
        self.filter_name = filter_name
        self.settings = template_settings or TemplateSettings()

        self.template_path.mkdir(parents=True, exist_ok=True)

        self.available_mods = self._discover_mods(path=assets_path)
        self.catalog_data = load_catalog(path=catalog_path)
        self.crate_icon: NDArray[np.uint8] | None = None
        self.subicon_cache: dict[str, NDArray[np.uint8] | None] = {}

        logger.info("Template generator initialized")
        logger.info("Assets path: %s", self.assets_path)
        logger.info("Output path: %s", self.template_path)
        logger.info("Available mods: %s", self.available_mods)
        logger.info("Catalog items: %d", len(self.catalog_data))
        if self.filter_name:
            logger.info("Filter applied: %s", self.filter_name)

    def _discover_mods(self, path: Path) -> list[str]:
        """Discover available mod folders in the assets directory.

        Args:
            path (Path): Path to the assets directory

        Returns:
            list[str]: List of available mod folder names, with vanilla prioritized
        """
        mod_folders: list[str] = []

        for item in path.iterdir():
            if item.is_dir():
                mod_folders.append(str(item.name))

        # Prioritize vanilla if it exists
        if TemplateGenerator.VANILLA_MOD_NAME in mod_folders:
            mod_folders.remove(TemplateGenerator.VANILLA_MOD_NAME)
            mod_folders.insert(0, TemplateGenerator.VANILLA_MOD_NAME)

        logger.info("Discovered %d mod folders: %s", len(mod_folders), mod_folders)
        return mod_folders

    async def _load_crate_icon(self) -> NDArray[np.uint8]:
        """Load the crate overlay icon, preferring vanilla folder.

        Returns:
            np.ndarray: Loaded crate icon as BGRA array

        Raises:
            FileNotFoundError: If the crate icon cannot be found in any mod folder
        """
        crate_icon_path = "War/Content/Textures/UI/Menus/IconFilterCrates"

        for mod_name in self.available_mods:
            crate_icon = await self._load_icon_image(icon_path=crate_icon_path, mod_name=mod_name)
            if crate_icon is not None:
                logger.info("Loaded crate icon from %s", mod_name)
                return crate_icon

        raise FileNotFoundError(f"Crate icon not found in any mod folder: {crate_icon_path}")

    def _calculate_icon_size(self, resolution: SupportedResolution) -> int:
        """Calculate icon size for given resolution.

        Args:
            resolution (SupportedResolution): Target resolution

        Returns:
            int: Icon size in pixels for the given resolution
        """
        return int(int(resolution.value) * self.ICON_SIZE_RATIO)

    async def _load_icon_image(self, icon_path: str, mod_name: str) -> NDArray[np.uint8] | None:
        """Load an icon image from the specified mod folder.

        Args:
            icon_path (str): Asset path from catalog
            mod_name (str): Name of the mod folder

        Returns:
            np.ndarray | None: Loaded image as RGBA array (converted to BGRA format), or None
                if not found
        """
        png_path = f"{icon_path}.png"
        full_path = self.assets_path / mod_name / png_path

        logger.debug("Trying to load icon from: %s", full_path)

        if not full_path.exists():
            logger.debug("Icon not found in %s: %s", mod_name, full_path)
            return None

        try:

            def load_with_pil() -> NDArray[np.uint8] | None:
                with Image.open(full_path) as img:
                    # Convert to RGBA to ensure consistent 4-channel format
                    img_rgba = img.convert("RGBA")
                    # Convert PIL image to numpy array (RGBA format)
                    image_array = np.array(img_rgba, dtype=np.uint8)
                    # Convert RGBA to BGRA (OpenCV format) for compatibility with rest of code
                    # Swap R and B channels
                    bgra = image_array[:, :, [2, 1, 0, 3]]
                    return bgra

            image = await asyncio.to_thread(load_with_pil)
            if image is None:
                logger.debug("Failed to load icon from %s: %s", mod_name, full_path)
                return None

            logger.debug("Successfully loaded icon from %s: %s", mod_name, full_path)
            return image

        except Exception as e:  # noqa: BLE001 - PIL/codec failures vary by image format
            logger.error("Error loading icon %s from %s: %s", full_path, mod_name, e)
            return None

    def _is_blank_subicon(self, subicon: NDArray[np.uint8]) -> bool:
        """Check if a subicon is blank or a solid color placeholder.

        Some mods (like clean-icons, improved-icons) provide blank or solid gray
        subicons to remove them. These should be detected and skipped.

        Detection methods:
        1. Mostly transparent (alpha < 10 for most pixels)
        2. Solid color with low variance (solid gray squares)

        Args:
            subicon (np.ndarray): Subicon image as BGRA array

        Returns:
            bool: True if subicon is blank/placeholder (should be skipped), False otherwise
        """
        if subicon is None or subicon.size == 0:
            return True

        # Method 1: Check alpha channel - count pixels with significant alpha
        alpha_channel = subicon[:, :, 3]
        total_pixels = alpha_channel.size
        visible_pixels = np.sum(alpha_channel > 10)
        visible_ratio = visible_pixels / total_pixels

        if visible_ratio < self.BLANK_SUBICON_THRESHOLD:
            logger.debug(
                "Detected blank subicon (transparent): %.1f%% visible",
                visible_ratio * 100,
            )
            return True

        # Method 2: Check if it's a solid color (low variance in RGB)
        # Only check pixels with significant alpha
        alpha_mask = alpha_channel > 10
        if np.sum(alpha_mask) > 0:
            # Get RGB values for visible pixels
            rgb_values = subicon[:, :, :3][alpha_mask]

            # Calculate standard deviation across all RGB values
            rgb_std = np.std(rgb_values)

            # If std is very low, it's essentially a solid color
            # Normal subicons have std > 30, solid colors have std < 10
            if rgb_std < 15:
                # Also check if it's a dark/gray color (not a valid icon color)
                rgb_mean = np.mean(rgb_values)
                if rgb_mean < 150:  # Dark gray threshold
                    logger.debug(
                        "Detected solid color subicon: std=%.1f, mean=%.1f",
                        rgb_std,
                        rgb_mean,
                    )
                    return True

        return False

    async def _load_subicon_cached(
        self, subicon_path: str, mod_name: str
    ) -> NDArray[np.uint8] | None:
        """Load a subicon with caching to avoid repeated disk access.

        Args:
            subicon_path (str): Asset path for subicon from catalog
            mod_name (str): Name of the mod folder

        Returns:
            np.ndarray | None: Loaded subicon as BGRA array, or None if not found or blank
        """
        cache_key = f"{mod_name}:{subicon_path}"

        # Check cache first
        if cache_key in self.subicon_cache:
            return self.subicon_cache[cache_key]

        # Try to load the subicon from this mod
        subicon = await self._load_icon_image(icon_path=subicon_path, mod_name=mod_name)

        if subicon is not None:
            # Check if subicon is blank (some mods like clean-icons provide blank subicons)
            if self._is_blank_subicon(subicon):
                logger.debug(
                    "Skipping blank subicon from %s: %s",
                    mod_name,
                    subicon_path,
                )
                # Cache as None so we don't re-check this file
                self.subicon_cache[cache_key] = None
                return None

            self.subicon_cache[cache_key] = subicon
            logger.debug("Cached subicon from %s: %s", mod_name, subicon_path)
            return subicon

        # If not found and not vanilla, try vanilla fallback
        if mod_name.lower() != TemplateGenerator.VANILLA_MOD_NAME:
            subicon = await self._load_subicon_cached(
                subicon_path=subicon_path,
                mod_name=TemplateGenerator.VANILLA_MOD_NAME,
            )
            if subicon is not None:
                self.subicon_cache[cache_key] = subicon
                logger.debug("Fallback to vanilla subicon for %s: %s", mod_name, subicon_path)
                return subicon

        # Not found anywhere
        self.subicon_cache[cache_key] = None
        return None

    def _filter_catalog_items(self, filter_name: str | None) -> list[CatalogItem]:
        """Filter catalog items based on filter_name if provided.

        Args:
            filter_name (str | None): String to filter items by CodeName

        Returns:
            list[CatalogItem]: Filtered catalog data
        """
        if not filter_name:
            return self.catalog_data

        filtered_items = [
            item for item in self.catalog_data if filter_name.lower() in item.code.lower()
        ]

        logger.info(
            "Filter '%s' matched %d out of %d items",
            self.filter_name,
            len(filtered_items),
            len(self.catalog_data),
        )

        if filtered_items:
            matched_names = [item.code for item in filtered_items]
            logger.info("Matched items: %s", ", ".join(matched_names))

        return filtered_items

    def _apply_subicon_effects(self, image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Apply color tint effects to subicon without alpha modification.

        Args:
            image (np.ndarray): Original subicon image as BGRA array

        Returns:
            np.ndarray: Processed image with multiplicative color tint
        """
        # Create a copy to avoid modifying the original
        result = image.copy().astype(np.float32)

        # Only process pixels that have significant alpha (avoid transparent areas)
        alpha_mask = result[:, :, 3] > 10

        # Apply color tint using settings (multipliers are divided by 255)
        result[alpha_mask, 0] = (
            result[alpha_mask, 0] * self.settings.crate_blue_multiplier / 255
            + self.settings.crate_blue_offset
        )
        result[alpha_mask, 1] = (
            result[alpha_mask, 1] * self.settings.crate_green_multiplier / 255
            + self.settings.crate_green_offset
        )
        result[alpha_mask, 2] = (
            result[alpha_mask, 2] * self.settings.crate_red_multiplier / 255
            + self.settings.crate_red_offset
        )

        # Clamp values and convert back to uint8
        result = np.clip(result, 0, 255)

        return result.astype(np.uint8)

    def _add_subicon(
        self,
        main_icon: NDArray[np.uint8],
        subicon: NDArray[np.uint8],
        target_size: int,
        top_left: bool = True,
    ) -> NDArray[np.uint8]:
        """Create icon with subicon overlay in top-left corner.

        Args:
            main_icon (np.ndarray): Main icon image as BGRA array
            subicon (np.ndarray): Subicon to overlay as BGRA array
            target_size (int): Target size for the final icon
            top_left (bool): If True, place subicon in top-left corner, else bottom-right

        Returns:
            np.ndarray: Combined icon with subicon overlay on black background
        """
        subicon_size = int(target_size * self.SUBICON_ASPECT_RATIO)

        # Apply color tint
        subicon_tinted = self._apply_subicon_effects(image=subicon)

        # Resize subicon using PIL
        # Convert BGRA to RGBA for PIL
        subicon_rgba = subicon_tinted[:, :, [2, 1, 0, 3]]
        subicon_pil = Image.fromarray(subicon_rgba.astype(np.uint8))
        subicon_pil_resized = subicon_pil.resize((subicon_size, subicon_size), Resampling.LANCZOS)
        # Convert back to BGRA numpy array
        subicon_resized = np.array(subicon_pil_resized, dtype=np.uint8)[:, :, [2, 1, 0, 3]]

        # Apply alpha blending for subicon overlay
        alpha_subicon = (subicon_resized[:, :, 3:4].astype(np.float32) / 255.0) * self.SUBICON_ALPHA

        # Blend subicon in top-left corner or bottom-right corner
        if top_left:
            x_pos = 0
            y_pos = 0
        else:
            x_pos = target_size - subicon_size
            y_pos = target_size - subicon_size

        for c in range(3):  # BGR channels
            main_icon[y_pos : y_pos + subicon_size, x_pos : x_pos + subicon_size, c] = (
                1 - alpha_subicon[:, :, 0]
            ) * main_icon[y_pos : y_pos + subicon_size, x_pos : x_pos + subicon_size, c] + (
                alpha_subicon[:, :, 0] * subicon_resized[:, :, c]
            )
        return main_icon

    def _create_base_icon(
        self, main_icon: NDArray[np.uint8], subicon: NDArray[np.uint8] | None, target_size: int
    ) -> NDArray[np.uint8]:
        """Create base icon with optional subicon overlay.

        Args:
            main_icon (np.ndarray): Main icon image as BGRA array
            subicon (np.ndarray | None): Optional subicon to overlay
            target_size (int): Target size for the final icon

        Returns:
            np.ndarray: Base icon with black background and optional subicon overlay
        """
        # Resize main icon using PIL for better quality
        # Convert BGRA to RGBA for PIL
        main_rgba = main_icon[:, :, [2, 1, 0, 3]]
        main_pil = Image.fromarray(main_rgba.astype(np.uint8))
        main_pil_resized = main_pil.resize((target_size, target_size), Resampling.LANCZOS)

        # Create black background and paste using alpha channel
        background = Image.new("RGB", (target_size, target_size), (0, 0, 0))
        background.paste(main_pil_resized, mask=main_pil_resized.split()[3])

        # Convert back to BGRA numpy array
        background_rgb = np.array(background, dtype=np.uint8)
        # Add alpha channel (fully opaque)
        base_icon = np.zeros((target_size, target_size, 4), dtype=np.uint8)
        base_icon[:, :, 2] = background_rgb[:, :, 0]  # R -> B
        base_icon[:, :, 1] = background_rgb[:, :, 1]  # G -> G
        base_icon[:, :, 0] = background_rgb[:, :, 2]  # B -> R
        base_icon[:, :, 3] = 255  # Alpha

        if subicon is not None:
            return self._add_subicon(main_icon=base_icon, subicon=subicon, target_size=target_size)

        return base_icon

    async def _generate_templates_for_item_and_mod(self, item: CatalogItem, mod_name: str) -> bool:
        """Generate all template variants for a single catalog item from a specific mod.

        Args:
            item (CatalogItem): Item data from catalog
            mod_name (str): Name of the mod folder

        Returns:
            bool: True if templates were generated successfully, False otherwise
        """
        code_name = item.code
        icon_path = item.icon_path
        subtype_icon_path = item.subicon_path

        if not code_name or not icon_path:
            logger.warning("Item missing CodeName or Icon: %s", item)
            return False

        logger.debug("Processing %s from mod %s (icon: %s)", code_name, mod_name, icon_path)

        # Load main icon from the specific mod
        main_icon = await self._load_icon_image(icon_path=icon_path, mod_name=mod_name)
        if main_icon is None:
            logger.warning(
                "Failed to load main icon for %s from %s: %s", code_name, mod_name, icon_path
            )
            return False

        # Load subicon if present
        subicon = None
        if subtype_icon_path:
            subicon = await self._load_subicon_cached(
                subicon_path=subtype_icon_path, mod_name=mod_name
            )
            if subicon is None:
                logger.debug(
                    "Failed to load subicon for %s from %s: %s",
                    code_name,
                    mod_name,
                    subtype_icon_path,
                )

        # Create output directories for this item
        normal_output_dir = self.template_path / code_name
        normal_output_dir.mkdir(exist_ok=True)

        # Only create crated directory for cratable items
        crated_output_dir = None
        if item.cratable:
            crated_output_dir = self.template_path / f"{code_name}_crated"
            crated_output_dir.mkdir(exist_ok=True)

        success_count = 0
        # 2 variants per resolution if cratable, 1 otherwise
        total_expected = len(SupportedResolution) * (2 if item.cratable else 1)

        # Generate templates for each resolution
        for resolution in SupportedResolution:
            icon_size = self._calculate_icon_size(resolution=resolution)

            try:
                # Create base icon (with or without subicon)
                base_icon = self._create_base_icon(
                    main_icon=main_icon, subicon=subicon, target_size=icon_size
                )

                # Save normal version
                normal_filename = f"{mod_name}_{code_name}_{icon_size}.png"
                normal_path = normal_output_dir / normal_filename
                await asyncio.to_thread(write_bgr, str(normal_path), base_icon)
                success_count += 1
                logger.debug("Saved: %s", normal_path)

                # Create and save crated version only for cratable items
                if item.cratable and crated_output_dir is not None:
                    if self.crate_icon is None:
                        raise RuntimeError("Crate icon not loaded")
                    crated_icon = self._add_subicon(
                        main_icon=base_icon,
                        subicon=self.crate_icon,
                        target_size=icon_size,
                        top_left=False,
                    )
                    crated_filename = f"{mod_name}_{code_name}_crated_{icon_size}.png"
                    crated_path = crated_output_dir / crated_filename
                    await asyncio.to_thread(write_bgr, str(crated_path), crated_icon)
                    success_count += 1
                    logger.debug("Saved: %s", crated_path)

                logger.debug(
                    "Generated templates for %s from %s at %dpx", code_name, mod_name, icon_size
                )

            except Exception as e:  # noqa: BLE001 - isolate one item/resolution from the batch
                logger.error(
                    "Error generating templates for %s from %s at %dpx: %s",
                    code_name,
                    mod_name,
                    icon_size,
                    e,
                )

        if success_count == total_expected:
            logger.debug(
                "Successfully generated all templates for %s from %s (%d/%d)",
                code_name,
                mod_name,
                success_count,
                total_expected,
            )
            return True
        logger.warning(
            "Partial success for %s from %s (%d/%d templates generated)",
            code_name,
            mod_name,
            success_count,
            total_expected,
        )
        return success_count > 0

    async def generate_all_templates(self) -> bool:
        """Generate templates for all catalog items across all available mods.

        Returns:
            bool: True if template generation completed successfully, False otherwise
        """
        if not self.available_mods:
            logger.error("No mod folders found in assets directory")
            return False

        # Load crate icon async if not already loaded
        if self.crate_icon is None:
            self.crate_icon = await self._load_crate_icon()

        # Apply filter if specified
        filtered_catalog = self._filter_catalog_items(filter_name=self.filter_name)
        if not filtered_catalog:
            logger.warning("No items match the filter criteria")
            return False

        total_successful_items = 0
        total_failed_items = 0
        total_processed = 0

        logger.info(
            "Starting template generation for %d items across %d mods",
            len(filtered_catalog),
            len(self.available_mods),
        )

        # Process each mod
        for mod_index, mod_name in enumerate(self.available_mods, 1):
            logger.info("Processing mod %d/%d: %s", mod_index, len(self.available_mods), mod_name)

            successful_items_in_mod = 0
            failed_items_in_mod = 0

            # Process items in the current mod concurrently
            semaphore = asyncio.Semaphore(4)  # Limit concurrent operations for I/O

            async def process_item_with_semaphore(
                item: CatalogItem,
                item_index: int,
                mod_name_param: str,
                semaphore_param: asyncio.Semaphore,
            ) -> bool:
                async with semaphore_param:
                    logger.debug(
                        "Processing item %d/%d in %s: %s",
                        item_index,
                        len(filtered_catalog),
                        mod_name_param,
                        item.code,
                    )
                    return await self._generate_templates_for_item_and_mod(
                        item=item, mod_name=mod_name_param
                    )

            # Create tasks for all items in this mod
            tasks = [
                process_item_with_semaphore(item, item_index, mod_name, semaphore)
                for item_index, item in enumerate(filtered_catalog, 1)
            ]

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks)

            # Count results
            for success in results:
                total_processed += 1
                if success:
                    successful_items_in_mod += 1
                    total_successful_items += 1
                else:
                    failed_items_in_mod += 1
                    total_failed_items += 1

            # Log mod summary
            logger.info(
                "Mod %s completed: %d successful, %d failed",
                mod_name,
                successful_items_in_mod,
                failed_items_in_mod,
            )

        # Log overall summary
        logger.info("Overall Template Generation Summary:")
        logger.info("Total processing attempts: %d", total_processed)
        logger.info("Successful generations: %d", total_successful_items)
        logger.info("Failed generations: %d", total_failed_items)
        logger.info(
            "Success rate: %.1f%%",
            (total_successful_items / total_processed) * 100 if total_processed > 0 else 0,
        )

        return total_failed_items == 0


async def main() -> None:
    """Command-line entry point for template generation."""
    parser = argparse.ArgumentParser(
        description="Generate icon templates from extracted Foxhole game assets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Generate all templates\n"
            "  fs generate-templates \\\n"
            "    --catalog training/catalog.json \\\n"
            "    --assets training/extracted_assets \\\n"
            "    --templates training/templates\n"
            "\n"
            "  # Generate templates for specific items\n"
            "  fs generate-templates \\\n"
            "    --catalog training/catalog.json \\\n"
            "    --assets training/extracted_assets \\\n"
            "    --templates training/templates \\\n"
            "    --filter Rifle\n"
            "\n"
            "  # Generate with verbose logging\n"
            "  fs generate-templates \\\n"
            "    --catalog training/catalog.json \\\n"
            "    --assets training/extracted_assets \\\n"
            "    --templates training/templates \\\n"
            "    --verbose --log-file generation.log"
        ),
    )

    parser.add_argument(
        "--catalog",
        type=Path,
        help="Path to catalog.json file (default: from database_builder.catalog_file setting)",
    )
    parser.add_argument(
        "--assets",
        type=Path,
        required=True,
        help="Path to the folder containing extracted assets (with mod subfolders)",
    )
    parser.add_argument(
        "--templates",
        type=Path,
        required=True,
        help="Path where generated templates will be saved",
    )
    parser.add_argument(
        "--filter",
        help="Filter items by CodeName containing this string (case-insensitive)",
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

    args = parser.parse_args()

    # Setup logging
    settings = get_settings()
    logging_settings = copy(settings.logging)
    # Setup logging
    if args.quiet:
        logging_settings.log_level = "WARNING"
    elif args.verbose:
        logging_settings.log_level = "DEBUG"

    logging_settings.log_file = args.log_file
    setup_logging(logging_settings)

    # Use catalog from args or fall back to config
    catalog_path = (
        args.catalog if args.catalog is not None else settings.database_builder.catalog_file
    )
    if catalog_path is None:
        logger.error(
            "Catalog path must be provided via --catalog or database_builder.catalog_file setting"
        )
        exit(1)

    # Validate input paths
    if not catalog_path.exists():
        logger.error("Catalog file not found: %s", catalog_path)
        exit(1)

    if not args.assets.exists():
        logger.error("Assets directory not found: %s", args.assets)
        exit(1)

    try:
        # Create generator and process templates
        generator = TemplateGenerator(
            catalog_path=catalog_path,
            assets_path=args.assets,
            template_path=args.templates,
            filter_name=args.filter,
            template_settings=TemplateSettings(),
        )

        success = await generator.generate_all_templates()

        if success:
            logger.info("Template generation completed successfully!")
            print("✅ Template generation completed successfully!")
        else:
            logger.error("Template generation completed with errors")
            print("❌ Template generation completed with errors. Check the logs for details.")
            exit(1)

    except Exception as e:  # noqa: BLE001 - CLI entry point, must report any failure before exit
        logger.exception("Template generation failed")
        print(f"❌ Template generation failed: {e}")
        exit(1)
