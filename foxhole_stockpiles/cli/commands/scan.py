"""``fs scan`` — run OCR on a Foxhole stockpile screenshot."""

import asyncio
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import typer

from foxhole_stockpiles.cli._settings import get_app_settings
from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    ReturnHandlerSettings,
)
from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.output_destination import OutputDestination
from foxhole_stockpiles.enums.output_format import OutputFormat
from foxhole_stockpiles.enums.supported_language import SupportedLanguage
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.scanner import Scanner

app = typer.Typer(help="Scan stockpile screenshots to identify items.")


def _create_handler_config_for_destination(
    destination: OutputDestination, output_file: Path | None = None
) -> OutputHandlerConfig:
    """Create a handler config for a specific output destination.

    Args:
        destination (OutputDestination): The output destination type.
        output_file (Path | None): Optional file path for file destination.

    Returns:
        OutputHandlerConfig: Handler configuration for the destination.
    """
    destination_names = {
        OutputDestination.RETURN: "CLI Return",
        OutputDestination.FILE: "CLI File Output",
        OutputDestination.CONSOLE: "CLI Console",
    }

    if destination == OutputDestination.FILE:
        return OutputHandlerConfig(
            name=destination_names.get(destination, "CLI Output"),
            format=JsonFormatSettings(),
            handler=FileHandlerSettings(path=str(output_file) if output_file else "output.json"),
        )
    elif destination == OutputDestination.CONSOLE:
        return OutputHandlerConfig(
            name=destination_names.get(destination, "CLI Output"),
            format=JsonFormatSettings(),
            handler=ConsoleHandlerSettings(),
        )
    else:  # RETURN is default
        return OutputHandlerConfig(
            name=destination_names.get(destination, "CLI Output"),
            format=JsonFormatSettings(),
            handler=ReturnHandlerSettings(),
        )


async def _run(
    image: str,
    database: Path | None,
    faction: str | None,
    language: SupportedLanguage | None,
    log_file: Path | None,
    verbose: bool,
    quiet: bool,
    output_destination: OutputDestination | None,
    output_file: Path | None,
    config: str | None,
    token: str | None,
) -> dict[str, Any] | None:
    """Run the OCR pipeline against a screenshot.

    Args:
        image (str): Path to the input image file.
        database (Path | None): Template database path (falls back to config).
        faction (str | None): Faction filter string.
        language (SupportedLanguage | None): Language for text detection.
        log_file (Path | None): Path to a log file.
        verbose (bool): Enable debug-level logging.
        quiet (bool): Suppress output except errors and warnings.
        output_destination (OutputDestination | None): Single-destination override.
        output_file (Path | None): File path for file destination.
        config (str | None): Path to a configuration file.
        token (str | None): Override the webhook token from the config.

    Returns:
        dict[str, Any] | None: Detected stockpile data, or None depending on the
            configured output handlers.

    Raises:
        typer.Exit: On missing inputs or pipeline failure.
    """
    try:
        settings = get_app_settings(config)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from e

    database_path = database if database is not None else settings.scanner.database_path
    if database_path is None:
        typer.echo(
            "Error: Database path must be provided via --database or in config file", err=True
        )
        raise typer.Exit(code=2)

    if not database_path.exists():
        typer.echo(f"Error: Database file not found: {database_path}", err=True)
        raise typer.Exit(code=1)
    if not database_path.is_file():
        typer.echo(f"Error: Database path is not a file: {database_path}", err=True)
        raise typer.Exit(code=1)

    # Fail fast if the image is missing before the expensive imread.
    if not Path(image).exists():
        typer.echo(f"Error: File '{image}' does not exist", err=True)
        raise typer.Exit(code=1)

    # Load and preprocess the image.
    _image = await asyncio.to_thread(cv2.imread, image, cv2.IMREAD_COLOR)
    if _image is None:
        typer.echo(f"Error: Could not load image from '{image}'", err=True)
        raise typer.Exit(code=1)

    image_array = np.asarray(_image, dtype=np.uint8)

    # Determine output settings.
    if output_destination:
        handler_config = _create_handler_config_for_destination(output_destination, output_file)
        output_settings = OutputSettings(handlers=[handler_config])
    elif output_file:
        handler_config = _create_handler_config_for_destination(OutputDestination.FILE, output_file)
        output_settings = OutputSettings(handlers=[handler_config])
    else:
        output_settings = settings.output

    log_level = "WARNING" if quiet else "DEBUG" if verbose else settings.logging.log_level
    logging_settings = settings.logging.model_copy(
        update={
            "log_level": log_level,
            "log_file": str(log_file) if log_file is not None else None,
        }
    )
    setup_logging(logging_settings)

    faction_filter = ItemFaction.from_string(faction)

    try:
        scanner_settings: ScannerSettings = settings.scanner.model_copy(
            update={"database_path": database_path}
        )

        scanner = Scanner(scanner_settings)
        stockpile: Stockpile = await scanner.scan(image_array, faction=faction_filter)
        output_coordinator = OutputCoordinator(output_settings=output_settings)

        output_kwargs: dict[str, Any] = {}
        if token:
            output_kwargs["token"] = token

        return await output_coordinator.handle_output(stockpiles=[stockpile], **output_kwargs)

    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:  # noqa: BLE001 - surface unexpected pipeline failures
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.callback(invoke_without_command=True)
def scan(
    image: str = typer.Option(..., "--image", help="Path to the input image file."),
    database: Path | None = typer.Option(
        None, "--database", help="Path to the template database file."
    ),
    faction: str | None = typer.Option(None, "--faction", help=ItemFaction.get_cli_help_text()),
    language: SupportedLanguage | None = typer.Option(
        None,
        "--language",
        help="Language for text detection. If not specified, uses all supported languages.",
    ),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Path to log file (default: console only)."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging (debug level)."),
    quiet: bool = typer.Option(
        False, "--quiet", help="Suppress all output except errors and warnings."
    ),
    output_format: OutputFormat | None = typer.Option(
        None, "--output-format", help="Data serialization format (default: json)."
    ),
    output_destination: OutputDestination | None = typer.Option(
        None, "--output-destination", help="Output destination (default: return)."
    ),
    output_file: Path | None = typer.Option(
        None,
        "--output-file",
        help="File path when using file destination (supports {timestamp}).",
    ),
    config: str | None = typer.Option(None, "--config", help="Path to configuration file."),
    token: str | None = typer.Option(
        None, "--token", help="Override the webhook token from the configuration file."
    ),
) -> None:
    """Scan a stockpile screenshot and emit the detected items.

    Args:
        image (str): Path to the input image file.
        database (Path | None): Template database path (falls back to config).
        faction (str | None): Faction filter string.
        language (SupportedLanguage | None): Language for text detection.
        log_file (Path | None): Path to a log file.
        verbose (bool): Enable debug-level logging.
        quiet (bool): Suppress output except errors and warnings.
        output_format (OutputFormat | None): Serialization format.
        output_destination (OutputDestination | None): Single-destination override.
        output_file (Path | None): File path for file destination.
        config (str | None): Path to a configuration file.
        token (str | None): Override the webhook token from the config.
    """
    # output_format is accepted for parity with the legacy CLI; JSON formatting is
    # applied by the output handlers. Format unification is handled in a later phase.
    del output_format

    result = asyncio.run(
        _run(
            image=image,
            database=database,
            faction=faction,
            language=language,
            log_file=log_file,
            verbose=verbose,
            quiet=quiet,
            output_destination=output_destination,
            output_file=output_file,
            config=config,
            token=token,
        )
    )

    if isinstance(result, dict):
        typer.echo(json.dumps(result, indent=2))
