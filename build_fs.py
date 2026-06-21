"""Build script for creating fs executable (unified CLI and GUI)."""

import os
import subprocess
import sys
from pathlib import Path


def get_hidden_imports() -> list[str]:
    """Get all hidden imports for the unified build."""
    return [
        # Core dependencies
        "cv2",
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
        # Notifications
        "discord_webhook",
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
        "foxhole_stockpiles.core.settings.sections.notifications",
        "foxhole_stockpiles.core.settings.sections.sav_processing",
        "foxhole_stockpiles.core.settings.sections.stockpile_types",
        "foxhole_stockpiles.core.settings.sections.database_builder",
        "foxhole_stockpiles.core.settings.sections.external_tools",
        "foxhole_stockpiles.core.settings.sections.ocr",
        "foxhole_stockpiles.core.settings.sections.templates",
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
        "foxhole_stockpiles.services.notification_service",
        "foxhole_stockpiles.services.memory_monitor",
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
        "foxhole_stockpiles.gui.widgets.config_tabs.notifications_tab",
        "foxhole_stockpiles.gui.widgets.config_tabs.sav_processing_tab",
        "foxhole_stockpiles.gui.widgets.config_tabs.stockpile_types_tab",
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


def build_executable(project_root: Path) -> bool:
    """Build the unified executable (fs.exe).

    Args:
        project_root: Path to project root directory

    Returns:
        True if build successful, False otherwise
    """
    print("=" * 50)
    print("Building Unified Executable (fs.exe)")
    print("=" * 50)
    print()
    print("This executable provides:")
    print("  - GUI mode: Run 'fs' with no arguments")
    print("  - CLI mode: Run 'fs <command>' for CLI commands")
    print()

    hidden_imports = get_hidden_imports()

    # Build PyInstaller command
    # Use --windowed so no console appears on double-click
    # CLI commands attach to parent console or allocate one when needed
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name",
        "fs",
        "--windowed",
    ]

    # Add data files (tessdata for OCR, translations for the GUI)
    # Use os.pathsep for cross-platform compatibility (';' on Windows, ':' on Unix)
    tessdata_src = project_root / "tessdata"
    tessdata_dst = "tessdata"
    cmd.extend(["--add-data", f"{tessdata_src}{os.pathsep}{tessdata_dst}"])

    translations_src = project_root / "foxhole_stockpiles" / "i18n" / "translations"
    translations_dst = os.path.join("foxhole_stockpiles", "i18n", "translations")
    cmd.extend(["--add-data", f"{translations_src}{os.pathsep}{translations_dst}"])

    # Recursively collect every submodule of the package. PyInstaller's static
    # analysis misses subpackages imported by name (e.g.
    # core.settings.sections.output), so collect them all explicitly.
    cmd.extend(["--collect-submodules", "foxhole_stockpiles"])

    # Add hidden imports (third-party packages with dynamic imports).
    for import_name in hidden_imports:
        cmd.extend(["--hidden-import", import_name])

    # Exclude development dependencies
    exclude_modules = ["pytest", "mypy", "ruff", "pre_commit"]
    for module in exclude_modules:
        cmd.extend(["--exclude-module", module])

    # Add the main script
    cmd.append("foxhole_stockpiles/__main__.py")

    print(f"Building with {len(hidden_imports)} hidden imports...")

    try:
        subprocess.run(cmd, cwd=project_root, check=True)

        # Check result
        exe_path = project_root / "dist" / "fs.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n[OK] Build successful!")
            print(f"  Executable: {exe_path}")
            print(f"  Size: {size_mb:.1f} MB")

            # Test the executable
            print("\n  Testing executable...")

            # Test help
            result = subprocess.run([str(exe_path), "--help"], capture_output=True, text=True)
            if result.returncode == 0:
                print("  [OK] Help command works")
            else:
                print("  [FAIL] Help command failed")
                return False

            # Test subcommand help
            result = subprocess.run(
                [str(exe_path), "scanner", "--help"], capture_output=True, text=True
            )
            if result.returncode == 0:
                print("  [OK] Scanner subcommand works")
            else:
                print("  [FAIL] Scanner subcommand failed")
                return False

            print("\n  Usage:")
            print("    fs          - Launch GUI (console window hidden)")
            print("    fs gui      - Launch GUI explicitly")
            print("    fs <cmd>    - Run CLI command")
            return True

        else:
            print("[FAIL] Executable not found after build")
            return False

    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Build failed: {e}")
        return False


def main() -> None:
    """Build the unified executable."""
    project_root = Path(__file__).parent

    print("Building Foxhole Stockpiles Executable")
    print("=" * 50)
    print()

    try:
        success = build_executable(project_root)

        print("\n" + "=" * 50)
        print("Build Summary")
        print("=" * 50)
        print(f"fs.exe: {'[OK] Success' if success else '[FAIL] Failed'}")

        if success:
            print("\nBuild completed successfully!")
            print("\nExecutable in dist/:")
            print("  - fs.exe: Unified CLI/GUI tool")
            print("            Run without args for GUI, with command for CLI")
        else:
            print("\nBuild failed. Check output above for details.")
            sys.exit(1)

    except FileNotFoundError:
        print("[FAIL] PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    main()
