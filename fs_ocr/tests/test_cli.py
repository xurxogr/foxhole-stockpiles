"""Tests for fs_ocr CLI.

This module tests the fs-ocr command-line interface.
"""

import json
import re

from typer.testing import CliRunner

from fs_ocr.cli import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR color codes from CLI output.

    Rich colorizes ``--help`` output when it detects a color-capable terminal,
    which CI does (it forces color via ``FORCE_COLOR``). Colorizing splits
    option names such as ``--database`` across separate style spans, so a raw
    substring check fails on CI while passing locally. Stripping the codes makes
    the assertions stable regardless of the environment's color settings.

    Args:
        text (str): Raw CLI output, possibly containing ANSI escape codes.

    Returns:
        str: The output with SGR color codes removed.
    """
    return _ANSI_RE.sub("", text)


class TestCLISchema:
    """Test suite for fs-ocr schema command."""

    def test_schema_outputs_valid_json(self) -> None:
        """Test that schema command outputs valid JSON."""
        result = runner.invoke(app, ["schema"])

        assert result.exit_code == 0
        schema = json.loads(result.stdout)
        assert "$schema" in schema
        assert schema["title"] == "Stockpile"

    def test_schema_has_required_properties(self) -> None:
        """Test that schema has expected properties."""
        result = runner.invoke(app, ["schema"])
        schema = json.loads(result.stdout)

        # Check that key properties are in the schema
        assert "properties" in schema
        properties = schema["properties"]
        assert "name" in properties
        assert "type" in properties
        assert "items" in properties


class TestCLIVersion:
    """Test suite for fs-ocr version command."""

    def test_version_outputs_info(self) -> None:
        """Test that version command outputs version info."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "fs-ocr" in result.stdout
        assert "schema" in result.stdout


class TestCLIHelp:
    """Test suite for fs-ocr help."""

    def test_help_shows_commands(self) -> None:
        """Test that help shows available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "scan" in output
        assert "schema" in output
        assert "info" in output
        assert "version" in output

    def test_scan_help_shows_options(self) -> None:
        """Test that scan --help shows required options."""
        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "--database" in output
        assert "--tessdata" in output
        assert "--early-exit" in output
