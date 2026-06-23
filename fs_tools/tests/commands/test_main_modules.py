"""Tests for the ``fs-tools`` command __main__.py entry points.

This module tests that the ``fs_tools`` command modules can be invoked via
``python -m`` syntax, ensuring the ``__main__.py`` files are properly configured
and importable. The main ``fs`` command entry points are covered by
``tests/commands/test_main_modules.py``.
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestMainModules:
    """Test suite for fs_tools command module entry points."""

    def test_database_builder_main_module(self) -> None:
        """Test that fs_tools.commands.database_builder can be run as module."""
        result = subprocess.run(
            [sys.executable, "-m", "fs_tools.commands.database_builder", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "database" in result.stdout.lower()

    def test_generate_templates_main_module(self) -> None:
        """Test that fs_tools.commands.generate_templates can be run as module."""
        result = subprocess.run(
            [sys.executable, "-m", "fs_tools.commands.generate_templates", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "template" in result.stdout.lower()

    def test_uasset_extractor_main_module(self) -> None:
        """Test that fs_tools.commands.uasset_extractor can be run as module."""
        result = subprocess.run(
            [sys.executable, "-m", "fs_tools.commands.uasset_extractor", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "extract" in result.stdout.lower()

    def test_add_icon_main_module(self) -> None:
        """Test that fs_tools.commands.add_icon can be run as module."""
        result = subprocess.run(
            [sys.executable, "-m", "fs_tools.commands.add_icon", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "icon" in result.stdout.lower()

    def test_catalog_builder_main_module(self) -> None:
        """Test that fs_tools.commands.catalog_builder can be run as module."""
        result = subprocess.run(
            [sys.executable, "-m", "fs_tools.commands.catalog_builder", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "catalog" in result.stdout.lower()


class TestMainModuleImports:
    """Test suite for fs_tools __main__.py module imports."""

    def test_database_builder_main_import(self) -> None:
        """Test importing database_builder __main__ module."""
        from fs_tools.commands.database_builder import (
            __main__ as database_builder_main,
        )

        assert hasattr(database_builder_main, "main")

    def test_generate_templates_main_import(self) -> None:
        """Test importing generate_templates __main__ module."""
        from fs_tools.commands.generate_templates import (
            __main__ as generate_templates_main,
        )

        assert hasattr(generate_templates_main, "main")

    def test_uasset_extractor_main_import(self) -> None:
        """Test importing uasset_extractor __main__ module."""
        from fs_tools.commands.uasset_extractor import (
            __main__ as uasset_extractor_main,
        )

        assert hasattr(uasset_extractor_main, "main")

    def test_add_icon_main_import(self) -> None:
        """Test importing add_icon __main__ module."""
        from fs_tools.commands.add_icon import __main__ as add_icon_main

        assert hasattr(add_icon_main, "main")

    def test_catalog_builder_main_import(self) -> None:
        """Test importing catalog_builder __main__ module."""
        from fs_tools.commands.catalog_builder import __main__ as catalog_builder_main

        assert hasattr(catalog_builder_main, "main")


class TestMainModuleFiles:
    """Test that all fs_tools __main__.py files exist and are valid Python."""

    MAIN_MODULE_PATHS = [
        "fs_tools/commands/database_builder/__main__.py",
        "fs_tools/commands/generate_templates/__main__.py",
        "fs_tools/commands/uasset_extractor/__main__.py",
        "fs_tools/commands/add_icon/__main__.py",
        "fs_tools/commands/catalog_builder/__main__.py",
    ]

    @pytest.mark.parametrize("module_path", MAIN_MODULE_PATHS)
    def test_main_file_exists(self, module_path: str) -> None:
        """Test that __main__.py file exists.

        Args:
            module_path (str): Path to the __main__.py file.
        """
        # Get project root (assumes test is in fs_tools/tests/commands/)
        project_root = Path(__file__).parents[3]
        main_file = project_root / module_path

        assert main_file.exists(), f"__main__.py not found at {main_file}"
        assert main_file.is_file(), f"__main__.py at {main_file} is not a file"

    @pytest.mark.parametrize("module_path", MAIN_MODULE_PATHS)
    def test_main_file_contains_required_code(self, module_path: str) -> None:
        """Test that __main__.py contains required structure.

        Args:
            module_path (str): Path to the __main__.py file.
        """
        project_root = Path(__file__).parents[3]
        main_file = project_root / module_path

        content = main_file.read_text()

        # Should have if __name__ == "__main__": guard
        assert '__name__ == "__main__"' in content or "__name__ == '__main__'" in content
        # Should import or reference main function
        assert "main" in content.lower()
