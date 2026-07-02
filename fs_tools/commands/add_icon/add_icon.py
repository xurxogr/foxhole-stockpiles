"""Add icon command for manually adding icons to template databases."""

from copy import copy
from pathlib import Path

import typer

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.constants import ICON_BOX_SCALE
from fs_tools.template_db.icon_manager import IconManager
from fs_tools.template_db.template_manager import TemplateManager


async def run(
    icon: Path,
    code: str,
    faction: str,
    category: str,
    mod: str,
    resolution: list[str],
    database: Path | None = None,
    crated: bool = False,
    replace: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    log_file: Path | None = None,
) -> None:
    """Add individual icons to the template database.

    Args:
        icon (Path): Path to icon image file.
        code (str): Item code name (e.g., Rifle, LightTank).
        faction (str): Faction for the icon (e.g., 'c', 'w', 'n').
        category (str): Category for the icon.
        mod (str): Mod name (e.g., vanilla, modname).
        resolution (list[str]): Target resolutions (can be specified multiple times).
        database (Path | None): Path to existing template database (.h5 file).
            Defaults to None (falls back to config).
        crated (bool): Mark this icon as a crated variant. Defaults to False.
        replace (bool): Replace existing icon if one already exists with same
            metadata. Defaults to False.
        verbose (bool): Enable verbose logging (debug level). Defaults to False.
        quiet (bool): Suppress all output except errors and warnings. Defaults
            to False.
        log_file (Path | None): Path to log file (default: console only).
            Defaults to None.

    Raises:
        typer.Exit: If the database path is missing/invalid, or the faction,
            category, or resolution values are invalid.
    """
    # Setup logging
    settings = get_settings()

    # Use database from args or fall back to config
    database_path = database if database is not None else settings.scanner.database_path
    if database_path is None:
        msg = "Database path must be provided via --database or in config file"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    # Validate database file exists (fail early with clearer error)
    if not database_path.exists():
        typer.echo(f"Error: Database file not found: {database_path}", err=True)
        raise typer.Exit(code=1)
    if not database_path.is_file():
        typer.echo(f"Error: Database path is not a file: {database_path}", err=True)
        raise typer.Exit(code=1)

    logging_settings = copy(settings.logging)
    if quiet:
        logging_settings.log_level = "WARNING"
    elif verbose:
        logging_settings.log_level = "DEBUG"

    logging_settings.log_file = str(log_file) if log_file is not None else None
    setup_logging(logging_settings)

    # Parse faction
    parsed_faction = ItemFaction.from_string(faction)
    if parsed_faction == ItemFaction.NEUTRAL and faction.lower() not in ["neutral", "n"]:
        # Invalid input resulted in NEUTRAL
        msg = f"Invalid faction '{faction}'. {ItemFaction.get_cli_help_text()}"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)

    # Parse category
    try:
        parsed_category = ItemCategory(category)
        if parsed_category == ItemCategory.Invalid:
            typer.echo(f"Invalid category '{category}'", err=True)
            raise typer.Exit(code=2)
    except ValueError:
        valid_categories = [c.value for c in ItemCategory if c != ItemCategory.Invalid]
        msg = f"Invalid category '{category}'. Valid categories are: {', '.join(valid_categories)}"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2) from None

    # Parse resolutions
    target_resolutions: list[SupportedResolution] = []
    for res_str in resolution:
        try:
            parsed_resolution = SupportedResolution(res_str)
            target_resolutions.append(parsed_resolution)
        except ValueError:
            valid_resolutions = [r.value for r in SupportedResolution]
            msg = (
                f"Invalid resolution '{res_str}'. "
                f"Valid resolutions are: {', '.join(valid_resolutions)}"
            )
            typer.echo(msg, err=True)
            raise typer.Exit(code=2) from None

    template_manager = TemplateManager(database_path=database_path)
    databases = await template_manager.load_all_resolutions()

    # Add icon using IconManager
    manager = IconManager(
        database_path=database_path,
        databases=databases,
        icon_scale=ICON_BOX_SCALE,
    )

    for target_resolution in target_resolutions:
        await manager.add_icon(
            icon_path=icon,
            item_code=code,
            faction=parsed_faction,
            category=parsed_category,
            crated=crated,
            mod=mod,
            resolution=target_resolution,
            replace=replace,
        )

    TemplateManager.save_databases_to_hdf5(
        databases=databases, output_path=database_path, workers=1
    )
