"""``fs sav`` — process Foxhole save files and extract stockpile data."""

import asyncio
from pathlib import Path

import typer

from foxhole_stockpiles.cli._settings import get_app_settings
from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings.sections.output import (
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
)
from foxhole_stockpiles.core.utils import auto_detect_savefile, find_mapdata_file
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor

app = typer.Typer(help="Process Foxhole save files for stockpile data.")


def _resolve_save_file(file: Path | None, save_dir: Path | None) -> Path:
    """Resolve the save file to process from the provided arguments.

    Args:
        file (Path | None): Explicit MapData.sav path.
        save_dir (Path | None): Directory to search for MapData.sav.

    Returns:
        Path: The resolved, existing save file path.

    Raises:
        typer.Exit: If no usable save file can be found.
    """
    save_file: Path | None = None

    if file:
        save_file = file
    elif save_dir:
        save_file = find_mapdata_file(save_dir)
        if save_file is None:
            typer.echo(f"Error: No MapData.sav file found in {save_dir}", err=True)
            raise typer.Exit(code=1)
    else:
        save_file = auto_detect_savefile()

    if save_file is None:
        typer.echo(
            "Error: Could not find save file. Use --file or --save-dir to specify.",
            err=True,
        )
        raise typer.Exit(code=1)

    if not save_file.exists():
        typer.echo(f"Error: File not found: {save_file}", err=True)
        raise typer.Exit(code=1)

    return save_file


async def _run(
    save_file: Path,
    output_settings: OutputSettings,
    poll_interval: float,
    once: bool,
) -> None:
    """Run the save-file processor.

    Args:
        save_file (Path): The MapData.sav file to process.
        output_settings (OutputSettings): Output handler configuration.
        poll_interval (float): Polling interval in seconds.
        once (bool): Process once and exit instead of monitoring.
    """
    output_coordinator = OutputCoordinator(output_settings)
    processor = SaveFileProcessor(
        file_path=save_file,
        output_coordinator=output_coordinator,
        poll_interval=poll_interval,
    )

    if once:
        await processor.run_once()
        return

    try:
        await processor.run()
    except KeyboardInterrupt:
        typer.echo("\nStopping processor...")
        processor.stop()


@app.callback(invoke_without_command=True)
def sav(
    file: Path | None = typer.Option(
        None, "--file", help="Path to the MapData.sav file (auto-detected if not specified)."
    ),
    save_dir: Path | None = typer.Option(
        None, "--save-dir", help="Path to Foxhole SaveGames directory."
    ),
    once: bool = typer.Option(False, "--once", help="Process file once and exit (no monitoring)."),
    poll_interval: float = typer.Option(
        1.0, "--poll-interval", help="Polling interval in seconds (default: 1.0)."
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Output file path (overrides config handlers, supports {timestamp}).",
    ),
    config: str | None = typer.Option(None, "--config", help="Path to configuration file."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    """Process Foxhole save files and extract stockpile data.

    Args:
        file (Path | None): Explicit MapData.sav path.
        save_dir (Path | None): Directory to search for MapData.sav.
        once (bool): Process once and exit instead of monitoring.
        poll_interval (float): Polling interval in seconds.
        output (Path | None): Output file path overriding configured handlers.
        config (str | None): Path to a configuration file.
        verbose (bool): Enable debug-level logging.
    """
    save_file = _resolve_save_file(file, save_dir)

    # Setup logging and settings.
    try:
        settings = get_app_settings(config)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from e

    log_level = "DEBUG" if verbose else settings.logging.log_level
    logging_settings = settings.logging.model_copy(update={"log_level": log_level})
    setup_logging(logging_settings)

    # --output overrides config handlers.
    if output:
        output_settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="CLI Output",
                    format=JsonFormatSettings(),
                    handler=FileHandlerSettings(path=str(output)),
                )
            ]
        )
    else:
        output_settings = settings.output

    asyncio.run(
        _run(
            save_file=save_file,
            output_settings=output_settings,
            poll_interval=poll_interval,
            once=once,
        )
    )
