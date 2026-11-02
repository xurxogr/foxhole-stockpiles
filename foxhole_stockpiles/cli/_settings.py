"""Shared helpers for loading application settings in CLI commands."""

import json
from pathlib import Path

import typer

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import AppSettings, get_settings
from foxhole_stockpiles.core.settings.sections.output import (
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
)


def get_app_settings(config_file: str | None = None) -> AppSettings:
    """Get application settings, optionally from a specified JSON config file.

    When ``config_file`` is given it is parsed as JSON and passed to
    ``AppSettings`` as init values (highest-priority source), so its contents
    override the defaults and run through config migration.

    Args:
        config_file (str | None): Path to a JSON configuration file. If None,
            the default cached settings are returned.

    Returns:
        AppSettings: Application settings.

    Raises:
        FileNotFoundError: If config_file is given but does not exist.
        ValueError: If config_file is not valid JSON or is not a JSON object.
    """
    if config_file is None:
        return get_settings()

    path = Path(config_file)
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {config_file}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object: {config_file}")

    return AppSettings(**data)


def load_settings_or_exit(config_file: str | None) -> AppSettings:
    """Get application settings, ending the command if they cannot be loaded.

    Args:
        config_file (str | None): Path to a JSON configuration file, if any.

    Returns:
        AppSettings: Application settings.

    Raises:
        typer.Exit: With code 2 if the settings cannot be loaded.
    """
    try:
        return get_app_settings(config_file)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from e


def setup_cli_logging(settings: AppSettings, verbose: bool) -> None:
    """Configure logging for a command.

    Args:
        settings (AppSettings): Application settings.
        verbose (bool): Log at debug level instead of the configured level.
    """
    log_level = "DEBUG" if verbose else settings.logging.log_level
    setup_logging(settings.logging.model_copy(update={"log_level": log_level}))


def resolve_output_settings(settings: AppSettings, output: Path | None) -> OutputSettings:
    """Get the output handlers of a command.

    Args:
        settings (AppSettings): Application settings.
        output (Path | None): The ``--output`` file, which overrides the configured
            handlers.

    Returns:
        OutputSettings: The handlers to use.
    """
    if output is None:
        return settings.output
    return OutputSettings(
        handlers=[
            OutputHandlerConfig(
                name="CLI Output",
                format=JsonFormatSettings(),
                handler=FileHandlerSettings(path=str(output)),
            )
        ]
    )
