"""Typer application for the unified ``fs`` command.

Replaces the previous custom ``CLIDispatcher``. Top-level commands are registered
as Typer sub-apps so each can expose its own options and aliases. Running ``fs``
with no subcommand launches the GUI (matching the legacy behavior).
"""

import multiprocessing

import typer

from foxhole_stockpiles import __version__
from foxhole_stockpiles.cli._console import attach_console
from foxhole_stockpiles.cli.commands import clip, gui, sav, scan

# Subcommand names that launch the GUI; the console is not attached for these.
_GUI_COMMANDS = frozenset({"gui"})

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="Foxhole Stockpiles - capture, process, and emit Foxhole stockpile data.",
)

app.add_typer(scan.app, name="scan")
app.add_typer(sav.app, name="sav")
app.add_typer(clip.app, name="clip")
app.add_typer(gui.app, name="gui")


@app.callback(invoke_without_command=True)
def _default(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Print version information and exit."
    ),
) -> None:
    """Root callback: handle ``--version`` and the no-subcommand GUI launch.

    Args:
        ctx (typer.Context): The Typer invocation context.
        version (bool): If True, print the version and exit.

    Raises:
        typer.Exit: When ``--version`` is supplied.
    """
    subcommand = ctx.invoked_subcommand

    # Attach a console for CLI subcommands on windowed Windows builds (no-op
    # elsewhere); skip it for the GUI so no console window pops up.
    if subcommand is not None and subcommand not in _GUI_COMMANDS:
        attach_console()

    if version:
        attach_console()
        typer.echo(f"Foxhole Stockpiles v{__version__}")
        raise typer.Exit()

    if subcommand is None:
        # No subcommand: launch the GUI (matches legacy behavior).
        gui.gui()


def main() -> None:
    """Entry point for the ``fs`` command."""
    # Required for multiprocessing to work in frozen executables (PyInstaller).
    multiprocessing.freeze_support()
    app()


if __name__ == "__main__":
    main()
