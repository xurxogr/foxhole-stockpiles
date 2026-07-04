"""``fs clip`` — read Foxhole stockpile data from the system clipboard.

Reads the in-game "copy stockpile" clipboard export, parses it, and routes the
result to the configured output handlers. Mirrors ``fs sav``: ``--once`` reads
the current clipboard a single time, otherwise the clipboard is polled and each
new export is emitted.
"""

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
from foxhole_stockpiles.services.clipboard_scan import (
    ClipboardScanService,
    build_clipboard_scan_service,
)
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator

app = typer.Typer(help="Read Foxhole stockpile data from the clipboard.")


async def _run(service: ClipboardScanService, poll_interval: float, once: bool) -> None:
    """Run the clipboard scan once or in a monitor loop.

    Args:
        service (ClipboardScanService): The clipboard scan service.
        poll_interval (float): Polling interval in seconds (monitor mode).
        once (bool): Read the clipboard once and exit instead of monitoring.
    """
    if once:
        stockpile = await service.scan_once()
        if stockpile is None:
            typer.echo("No stockpile data found in clipboard.")
        return

    # Seed the last-seen clipboard so only a new export emits.
    service.prime()
    typer.echo("Monitoring clipboard for stockpile exports... Press Ctrl+C to stop.")
    try:
        while True:
            await service.poll()
            await asyncio.sleep(poll_interval)
    except (KeyboardInterrupt, asyncio.CancelledError):
        typer.echo("\nStopping clipboard monitor...")


@app.callback(invoke_without_command=True)
def clip(
    once: bool = typer.Option(
        False, "--once", help="Read the clipboard once and exit (no monitoring)."
    ),
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
    """Read Foxhole stockpile data from the clipboard and emit it.

    Args:
        once (bool): Read the clipboard once and exit instead of monitoring.
        poll_interval (float): Polling interval in seconds.
        output (Path | None): Output file path overriding configured handlers.
        config (str | None): Path to a configuration file.
        verbose (bool): Enable debug-level logging.
    """
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

    try:
        service = build_clipboard_scan_service(settings, OutputCoordinator(output_settings))
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2) from e

    asyncio.run(_run(service=service, poll_interval=poll_interval, once=once))
