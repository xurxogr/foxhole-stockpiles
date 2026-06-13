"""Tests for the root Typer application (``foxhole_stockpiles.cli.app``).

Covers help output, alias registration, the ``--version`` flag, and the
no-subcommand GUI launch behaviour.
"""

import re
from unittest.mock import patch

from typer.testing import CliRunner

from foxhole_stockpiles import __version__
from foxhole_stockpiles.cli.app import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR color codes from CLI output.

    Rich colorizes ``--help`` output when it detects a color-capable terminal,
    which CI does (it forces color via ``FORCE_COLOR``). Colorizing splits
    option names such as ``--image`` across separate style spans, so a raw
    substring check fails on CI while passing locally. Stripping the codes makes
    the assertions stable regardless of the environment's color settings.

    Args:
        text (str): Raw CLI output, possibly containing ANSI escape codes.

    Returns:
        str: The output with SGR color codes removed.
    """
    return _ANSI_RE.sub("", text)


class TestRootHelp:
    """Test suite for the root ``fs`` help output."""

    def test_help_lists_canonical_commands(self) -> None:
        """Help text lists the canonical subcommands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        for command in ("scan", "sav", "serve", "gui"):
            assert command in output

    def test_help_hides_aliases(self) -> None:
        """Hidden alias commands do not appear in the help listing."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        for alias in ("scanner", "process-sav"):
            assert alias not in output


class TestVersion:
    """Test suite for the ``--version`` flag."""

    def test_version_flag(self) -> None:
        """``--version`` prints the version and exits cleanly."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert f"Foxhole Stockpiles v{__version__}" in strip_ansi(result.output)


class TestNoSubcommand:
    """Test suite for invoking ``fs`` with no subcommand."""

    def test_no_args_launches_gui(self) -> None:
        """Running with no subcommand launches the GUI."""
        with patch("foxhole_stockpiles.cli.commands.gui.launch_gui") as mock_launch:
            result = runner.invoke(app, [])

            assert result.exit_code == 0
            mock_launch.assert_called_once()


class TestAliases:
    """Test suite for command alias resolution."""

    def test_scanner_alias_resolves_to_scan(self) -> None:
        """The ``scanner`` alias exposes the same options as ``scan``."""
        result = runner.invoke(app, ["scanner", "--help"])

        assert result.exit_code == 0
        assert "--image" in strip_ansi(result.output)

    def test_server_alias_resolves_to_serve(self) -> None:
        """The ``server`` alias exposes the same options as ``serve``."""
        result = runner.invoke(app, ["server", "--help"])

        assert result.exit_code == 0
        assert "--host" in strip_ansi(result.output)


class TestMainEntryPoint:
    """Test suite for the ``main`` entry point."""

    def test_main_calls_freeze_support(self) -> None:
        """``main`` invokes ``multiprocessing.freeze_support`` before the app."""
        import multiprocessing
        import sys

        # The ``cli`` package re-exports ``app``, which shadows the submodule on
        # attribute access; fetch the real module object from ``sys.modules``.
        app_module = sys.modules["foxhole_stockpiles.cli.app"]

        with (
            patch.object(multiprocessing, "freeze_support") as mock_freeze,
            patch.object(app_module, "app") as mock_app,
        ):
            app_module.main()

            mock_freeze.assert_called_once()
            mock_app.assert_called_once()
