"""Add icon command for manually adding icons to template databases."""

import argparse
import sys
from copy import copy
from pathlib import Path

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.settings.sections.ocr import OCRSettings
from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.template_db.icon_manager import IconManager
from fs_tools.template_db.template_manager import TemplateManager


async def main() -> None:
    """Main entry point for add icon command."""
    parser = argparse.ArgumentParser(
        description="Add individual icons to template database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add a normal Colonial rifle icon at 1080p (icon must be 32x32)
  fs add-icon --database data/templates.h5 --icon rifle_32x32.png \\
    --code Rifle --faction c --category item \\
    --mod vanilla --resolution 1080

  # Add a crated Warden shippable icon at 2160p (icon must be 64x64)
  fs add-icon --database data/templates.h5 --icon crate_64x64.png \\
    --code ShippableCrate --faction w --category shippable \\
    --crated --mod vanilla --resolution 2160

  # Add a neutral item at multiple resolutions (need separate sized icons)
  fs add-icon --database data/templates.h5 --icon medkit_32x32.png \\
    --code Medkit --faction n --category item \\
    --mod vanilla --resolution 1080

  fs add-icon --database data/templates.h5 --icon medkit_43x43.png \\
    --code Medkit --faction n --category item \\
    --mod vanilla --resolution 1440

Note: Icon dimensions must exactly match the target resolution requirements.
      Use: 664p=19px, 720p=21px, 1080p=32px, 1440p=43px, 2160p=64px
        """,
    )

    parser.add_argument(
        "--database",
        type=Path,
        help="Path to existing template database (.h5 file)",
    )
    parser.add_argument(
        "--icon",
        type=Path,
        required=True,
        help="Path to icon image file",
    )
    parser.add_argument(
        "--code",
        type=str,
        required=True,
        help="Item code name (e.g., Rifle, LightTank)",
    )
    parser.add_argument(
        "--faction",
        type=str,
        required=True,
        choices=[faction.value for faction in ItemFaction],
        help="Faction for the icon. Valid factions: "
        + ", ".join([f"'{f.value}'" for f in ItemFaction]),
    )
    parser.add_argument(
        "--category",
        type=str,
        required=True,
        choices=[category.value for category in ItemCategory if category != ItemCategory.Invalid],
        help="Category for the icon. Valid categories: "
        + ", ".join([f"'{c.value}'" for c in ItemCategory if c != ItemCategory.Invalid]),
    )
    parser.add_argument(
        "--crated",
        action="store_true",
        help="Mark this icon as a crated variant",
    )
    parser.add_argument(
        "--mod",
        type=str,
        required=True,
        help="Mod name (e.g., vanilla, modname)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing icon if one already exists with same metadata. "
        "Without this flag, attempting to add a duplicate will result in an error.",
    )
    parser.add_argument(
        "--resolution",
        action="append",
        required=True,
        help=(
            "Target resolution (can be specified multiple times, e.g., "
            "--resolution 1080 --resolution 2160)"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (debug level)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress all output except errors and warnings",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Path to log file (default: console only)",
    )

    args = parser.parse_args()

    # Setup logging
    settings = get_settings()

    # Use database from args or fall back to config
    database_path = args.database if args.database is not None else settings.scanner.database_path
    if database_path is None:
        parser.error("Database path must be provided via --database or in config file")

    # Validate database file exists (fail early with clearer error)
    if not database_path.exists():
        print(f"Error: Database file not found: {database_path}", file=sys.stderr)
        sys.exit(1)
    if not database_path.is_file():
        print(f"Error: Database path is not a file: {database_path}", file=sys.stderr)
        sys.exit(1)

    logging_settings = copy(settings.logging)
    if args.quiet:
        logging_settings.log_level = "WARNING"
    elif args.verbose:
        logging_settings.log_level = "DEBUG"

    logging_settings.log_file = args.log_file
    setup_logging(logging_settings)

    # Parse faction
    faction = ItemFaction.from_string(args.faction)
    if faction == ItemFaction.NEUTRAL and args.faction.lower() not in ["neutral", "n"]:
        # Invalid input resulted in NEUTRAL
        parser.error(f"Invalid faction '{args.faction}'. {ItemFaction.get_cli_help_text()}")

    # Parse category
    try:
        category = ItemCategory(args.category)
        if category == ItemCategory.Invalid:
            parser.error(f"Invalid category '{args.category}'")
    except ValueError:
        valid_categories = [c.value for c in ItemCategory if c != ItemCategory.Invalid]
        parser.error(
            f"Invalid category '{args.category}'. "
            f"Valid categories are: {', '.join(valid_categories)}"
        )

    # Parse resolutions
    target_resolutions: list[SupportedResolution] = []
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

    template_manager = TemplateManager(database_path=database_path)
    databases = await template_manager.load_all_resolutions()

    # Add icon using IconManager
    ocr = OCRSettings()
    manager = IconManager(
        database_path=database_path,
        databases=databases,
        icon_scale=ocr.box_height / ocr.height,
    )

    for resolution in target_resolutions:
        await manager.add_icon(
            icon_path=args.icon,
            item_code=args.code,
            faction=faction,
            category=category,
            crated=args.crated,
            mod=args.mod,
            resolution=resolution,
            replace=args.replace,
        )

    TemplateManager.save_databases_to_hdf5(
        databases=databases, output_path=database_path, workers=1
    )
