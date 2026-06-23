"""Build script for the project executables.

Builds two standalone executables with PyInstaller:

* ``fs``       - desktop runtime: unified CLI + PySide6 GUI.
* ``fs-tools`` - build-time tooling CLI + GUI (catalog/template database tools).
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


def get_fs_hidden_imports() -> list[str]:
    """Get all hidden imports for the ``fs`` runtime build.

    Returns:
        list[str]: Module names to force-include in the build.
    """
    return [
        # Core dependencies
        "numpy",
        "numpy.core._methods",
        "numpy.lib.format",
        "pydantic",
        "pydantic.json_schema",
        "pydantic_settings",
        "pytesseract",
        "h5py",
        "httpx",
        "PIL",
        "PIL.ImageGrab",
        # External Rust engines
        "fs_ocr",
        "fs_sav",
        # Screenshot capture (window detection + global hotkey)
        "pynput",
        "pynput.keyboard",
        "pywinctl",
        # Google Sheets output handler
        "google.oauth2.credentials",
        "google.auth.transport.requests",
        "google_auth_oauthlib.flow",
        "googleapiclient.discovery",
        "googleapiclient.errors",
        # Core package modules
        "foxhole_stockpiles",
        "foxhole_stockpiles.core",
        "foxhole_stockpiles.core.logging",
        "foxhole_stockpiles.core.utils",
        "foxhole_stockpiles.enums",
        "foxhole_stockpiles.enums.item_faction",
        "foxhole_stockpiles.enums.item_category",
        "foxhole_stockpiles.enums.supported_resolution",
        "foxhole_stockpiles.models",
        # Settings + sections (the output subpackage is imported by name and is
        # not reliably picked up by PyInstaller's static analysis).
        "foxhole_stockpiles.core.settings",
        "foxhole_stockpiles.core.settings.app_settings",
        "foxhole_stockpiles.core.settings.config_migrator",
        "foxhole_stockpiles.core.settings.json_settings_source",
        "foxhole_stockpiles.core.settings.sections",
        "foxhole_stockpiles.core.settings.sections.scanner",
        "foxhole_stockpiles.core.settings.sections.logging",
        "foxhole_stockpiles.core.settings.sections.gui",
        "foxhole_stockpiles.core.settings.sections.sav_processing",
        "foxhole_stockpiles.core.settings.sections.database_builder",
        "foxhole_stockpiles.core.settings.sections.external_tools",
        "foxhole_stockpiles.core.settings.sections.output",
        "foxhole_stockpiles.core.settings.sections.output.settings",
        "foxhole_stockpiles.core.settings.sections.output.handler_config",
        "foxhole_stockpiles.core.settings.sections.output.console_handler",
        "foxhole_stockpiles.core.settings.sections.output.file_handler",
        "foxhole_stockpiles.core.settings.sections.output.webhook_handler",
        "foxhole_stockpiles.core.settings.sections.output.return_handler",
        "foxhole_stockpiles.core.settings.sections.output.sheets_handler",
        "foxhole_stockpiles.core.settings.sections.output.json_format",
        "foxhole_stockpiles.core.settings.sections.output.csv_format",
        # Services (OCR seam, capture, local scan, output, SAV)
        "foxhole_stockpiles.services",
        "foxhole_stockpiles.services.scanner",
        "foxhole_stockpiles.services.capture",
        "foxhole_stockpiles.services.local_scan",
        "foxhole_stockpiles.services.output_coordinator",
        "foxhole_stockpiles.services.catalog_service",
        "foxhole_stockpiles.services.sav_parser",
        "foxhole_stockpiles.services.savefile_processor",
        # Output handlers
        "foxhole_stockpiles.handlers.console",
        "foxhole_stockpiles.handlers.file",
        "foxhole_stockpiles.handlers.webhook",
        "foxhole_stockpiles.handlers.response",
        "foxhole_stockpiles.handlers.sheets",
        # Typer CLI application and command modules
        "foxhole_stockpiles.cli",
        "foxhole_stockpiles.cli.app",
        "foxhole_stockpiles.cli._console",
        "foxhole_stockpiles.cli.commands.scan",
        "foxhole_stockpiles.cli.commands.sav",
        "foxhole_stockpiles.cli.commands.gui",
        # PySide6 dependencies (for GUI)
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        # GUI modules
        "foxhole_stockpiles.gui",
        "foxhole_stockpiles.gui.app",
        "foxhole_stockpiles.gui.windows",
        "foxhole_stockpiles.gui.windows.main_window",
        "foxhole_stockpiles.gui.windows.config_window",
        "foxhole_stockpiles.gui.widgets",
        "foxhole_stockpiles.gui.widgets.capture_panel",
        "foxhole_stockpiles.gui.widgets.config_tabs",
        "foxhole_stockpiles.gui.widgets.config_tabs.scanner_tab",
        "foxhole_stockpiles.gui.widgets.config_tabs.output_tab",
        "foxhole_stockpiles.gui.widgets.config_tabs.gui_tab",
        "foxhole_stockpiles.gui.widgets.config_tabs.logging_tab",
        "foxhole_stockpiles.gui.widgets.config_tabs.sav_processing_tab",
        "foxhole_stockpiles.gui.utils",
        "foxhole_stockpiles.gui.utils.qt_log_handler",
        "foxhole_stockpiles.gui.utils.config_manager",
        "foxhole_stockpiles.gui.utils.capture_scan_worker",
        "foxhole_stockpiles.gui.utils.hotkey_listener",
        "foxhole_stockpiles.gui.utils.image_scan_worker",
        "foxhole_stockpiles.gui.utils.sav_workers",
        # Internationalization
        "foxhole_stockpiles.i18n",
        "foxhole_stockpiles.i18n.translator",
    ]


def get_fs_tools_hidden_imports() -> list[str]:
    """Get all hidden imports for the ``fs-tools`` tooling build.

    Returns:
        list[str]: Module names to force-include in the build.
    """
    return [
        # Core dependencies
        "numpy",
        "numpy.core._methods",
        "numpy.lib.format",
        "pydantic",
        "pydantic.json_schema",
        "pydantic_settings",
        "h5py",
        "PIL",
        "typer",
        # PySide6 dependencies (for the tooling GUI)
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        # Shared runtime package (fs_tools reuses its settings/i18n/models)
        "foxhole_stockpiles",
        "foxhole_stockpiles.core.settings.app_settings",
        "foxhole_stockpiles.i18n",
        "foxhole_stockpiles.i18n.translator",
        # fs_tools package itself
        "fs_tools",
        "fs_tools.cli",
        "fs_tools.gui",
        # Tool command modules are imported by name (importlib) from cli.py and
        # are not seen by PyInstaller's static analysis.
        "fs_tools.commands.catalog_builder.catalog_builder",
        "fs_tools.commands.database_builder.database_builder",
        "fs_tools.commands.generate_templates.generate_templates",
        "fs_tools.commands.uasset_extractor.uasset_extractor",
        "fs_tools.commands.add_icon.add_icon",
        "fs_tools.commands.add_mod.add_mod",
    ]


@dataclass(frozen=True)
class BuildSpec:
    """Definition of a single PyInstaller executable build.

    Attributes:
        name (str): Executable name (PyInstaller ``--name``).
        entry_script (str): Path to the entry script, relative to project root.
        collect_packages (list[str]): Packages to ``--collect-submodules``.
        hidden_imports (list[str]): Modules to force-include via ``--hidden-import``.
        data_dirs (list[tuple[str, str]]): ``(source, dest)`` data directory pairs,
            with ``source`` relative to project root.
        test_args (list[list[str]]): Argument lists to smoke-test the built exe.
    """

    name: str
    entry_script: str
    collect_packages: list[str]
    hidden_imports: list[str]
    data_dirs: list[tuple[str, str]] = field(default_factory=list)
    test_args: list[list[str]] = field(default_factory=list)


def build_executable(project_root: Path, spec: BuildSpec) -> bool:
    """Build a standalone executable from a build spec.

    Args:
        project_root (Path): Path to the project root directory.
        spec (BuildSpec): The executable build definition.

    Returns:
        bool: True if the build succeeded and smoke tests passed, False otherwise.
    """
    print("=" * 50)
    print(f"Building Executable ({spec.name}.exe)")
    print("=" * 50)
    print()

    # Use --windowed so no console appears on double-click; CLI commands attach
    # to the parent console (or allocate one) when needed.
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name",
        spec.name,
        "--windowed",
    ]

    # Add data directories (tessdata, translations, ...).
    # Use os.pathsep for cross-platform compatibility (';' on Windows, ':' on Unix).
    for src_rel, dst in spec.data_dirs:
        src = project_root / src_rel
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    # Recursively collect every submodule of the listed packages. PyInstaller's
    # static analysis misses subpackages imported by name, so collect them all.
    for package in spec.collect_packages:
        cmd.extend(["--collect-submodules", package])

    # Add hidden imports (third-party packages with dynamic imports).
    for import_name in spec.hidden_imports:
        cmd.extend(["--hidden-import", import_name])

    # Exclude development dependencies.
    exclude_modules = ["pytest", "mypy", "ruff", "pre_commit"]
    for module in exclude_modules:
        cmd.extend(["--exclude-module", module])

    # Add the main script.
    cmd.append(spec.entry_script)

    print(f"Building with {len(spec.hidden_imports)} hidden imports...")

    try:
        subprocess.run(cmd, cwd=project_root, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Build failed: {e}")
        return False

    exe_path = project_root / "dist" / f"{spec.name}.exe"
    if not exe_path.exists():
        print("[FAIL] Executable not found after build")
        return False

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\n[OK] Build successful!")
    print(f"  Executable: {exe_path}")
    print(f"  Size: {size_mb:.1f} MB")

    # Smoke-test the executable.
    print("\n  Testing executable...")
    for args in spec.test_args:
        result = subprocess.run(
            [str(exe_path), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        label = " ".join(args) or "(no args)"
        if result.returncode == 0:
            print(f"  [OK] '{label}' works")
        else:
            print(f"  [FAIL] '{label}' failed")
            return False

    return True


def get_build_specs() -> list[BuildSpec]:
    """Get the build specs for every executable produced by this script.

    Returns:
        list[BuildSpec]: The ``fs`` and ``fs-tools`` executable build specs.
    """
    return [
        BuildSpec(
            name="fs",
            entry_script="foxhole_stockpiles/__main__.py",
            collect_packages=["foxhole_stockpiles"],
            hidden_imports=get_fs_hidden_imports(),
            data_dirs=[
                ("tessdata", "tessdata"),
                (
                    os.path.join("foxhole_stockpiles", "i18n", "translations"),
                    os.path.join("foxhole_stockpiles", "i18n", "translations"),
                ),
            ],
            test_args=[["--help"], ["scan", "--help"]],
        ),
        BuildSpec(
            name="fs-tools",
            # fs_tools/cli.py runs main() under `if __name__ == "__main__"`.
            entry_script=os.path.join("fs_tools", "cli.py"),
            collect_packages=["fs_tools", "foxhole_stockpiles"],
            hidden_imports=get_fs_tools_hidden_imports(),
            data_dirs=[
                (
                    os.path.join("fs_tools", "i18n", "translations"),
                    os.path.join("fs_tools", "i18n", "translations"),
                ),
            ],
            test_args=[["--help"], ["build-db", "--help"]],
        ),
    ]


def main() -> None:
    """Build every project executable and print a summary."""
    project_root = Path(__file__).parent

    print("Building Foxhole Stockpiles Executables")
    print("=" * 50)
    print()

    specs = get_build_specs()
    results: dict[str, bool] = {}

    try:
        for spec in specs:
            results[spec.name] = build_executable(project_root, spec)
            print()
    except FileNotFoundError:
        print("[FAIL] PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)

    print("=" * 50)
    print("Build Summary")
    print("=" * 50)
    for name, success in results.items():
        print(f"{name}.exe: {'[OK] Success' if success else '[FAIL] Failed'}")

    if all(results.values()):
        print("\nBuild completed successfully!")
        print("\nExecutables in dist/:")
        print("  - fs.exe:       Unified CLI/GUI runtime")
        print("                  Run without args for GUI, with command for CLI")
        print("  - fs-tools.exe: Catalog/template database tooling")
        print("                  Run without args for GUI, with command for CLI")
    else:
        print("\nBuild failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
