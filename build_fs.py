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


def get_unused_qt_modules() -> list[str]:
    """Get PySide6 Qt modules to exclude from every build.

    The GUIs use only ``QtCore``/``QtGui``/``QtWidgets``. These modules are
    never imported and are not transitive dependencies of Widgets, so excluding
    them is safe; it only saves space if PyInstaller's PySide6 hook would
    otherwise over-collect them. Modules that Widgets/Gui *can* pull in
    transitively (Svg, OpenGL, PrintSupport, Network, DBus, Xml) are
    deliberately left in.

    Returns:
        list[str]: ``PySide6.*`` module names to pass to ``--exclude-module``.
    """
    return [
        # Web engine (the 194 MB monster) and friends.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebView",
        "PySide6.QtWebChannel",
        "PySide6.QtWebSockets",
        # QML / Quick stack (we are a Widgets app).
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQuickTest",
        # 3D.
        "PySide6.Qt3DCore",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        # Multimedia (pulls in libavcodec).
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtSpatialAudio",
        # Charts / data visualization / graphs.
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtGraphsWidgets",
        # PDF, designer, help, test tooling.
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtDesigner",
        "PySide6.QtUiTools",
        "PySide6.QtHelp",
        "PySide6.QtTest",
        # Connectivity / sensors / location.
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtSerialPort",
        "PySide6.QtSerialBus",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtLocation",
        # Misc unused subsystems.
        "PySide6.QtSql",
        "PySide6.QtScxml",
        "PySide6.QtStateMachine",
        "PySide6.QtRemoteObjects",
        "PySide6.QtTextToSpeech",
        "PySide6.QtHttpServer",
        "PySide6.QtNetworkAuth",
    ]


@dataclass(frozen=True)
class BuildSpec:
    """Definition of a single PyInstaller executable build.

    Attributes:
        name (str): Executable name (PyInstaller ``--name``).
        entry_script (str): Path to the entry script, relative to project root.
        collect_packages (list[str]): Packages to ``--collect-submodules``.
        hidden_imports (list[str]): Modules to force-include via ``--hidden-import``.
        exclude_modules (list[str]): Modules to drop via ``--exclude-module`` (on
            top of the shared dev-tool excludes).
        data_dirs (list[tuple[str, str]]): ``(source, dest)`` data directory pairs,
            with ``source`` relative to project root.
        test_args (list[list[str]]): Argument lists to smoke-test the built exe.
    """

    name: str
    entry_script: str
    collect_packages: list[str]
    hidden_imports: list[str]
    exclude_modules: list[str] = field(default_factory=list)
    data_dirs: list[tuple[str, str]] = field(default_factory=list)
    test_args: list[list[str]] = field(default_factory=list)


def render_spec(project_root: Path, spec: BuildSpec) -> str:
    """Render a PyInstaller ``.spec`` file for a build spec.

    A spec (rather than CLI flags) is required so we can filter the *binaries*
    PyInstaller bundles: ``--exclude-module`` only drops Python wrappers, leaving
    the Qt shared libraries (Qt6Qml/Quick/Pdf/ShaderTools, the QML plugin tree
    and Qt's own translations) that a QWidgets app never uses. Those are stripped
    here; platform/style/imageformat plugins and Qt6Core/Gui/Widgets are kept.

    Args:
        project_root (Path): Path to the project root directory.
        spec (BuildSpec): The executable build definition.

    Returns:
        str: The contents of the ``.spec`` file.
    """
    entry = (project_root / spec.entry_script).as_posix()
    datas = [((project_root / src).as_posix(), dst) for src, dst in spec.data_dirs]
    excludes = ["pytest", "mypy", "ruff", "pre_commit", *spec.exclude_modules]
    hidden = list(spec.hidden_imports)
    collect = list(spec.collect_packages)

    # chr(92) is a backslash; using it avoids backslash escaping inside this
    # template while still normalising Windows TOC paths to forward slashes.
    return f"""# -*- mode: python ; coding: utf-8 -*-
# Auto-generated by build_fs.py. Do not edit by hand; regenerate via build_fs.py.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = {hidden!r}
for _pkg in {collect!r}:
    hiddenimports += collect_submodules(_pkg)

a = Analysis(
    [{entry!r}],
    pathex=[],
    binaries=[],
    datas={datas!r},
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes={excludes!r},
    noarchive=False,
)

# Strip Qt subsystems a QWidgets app never uses (QML/Quick/Pdf/ShaderTools
# shared libs, the QML plugin tree, the qmltooling plugins and Qt's bundled
# translations). PyInstaller's PySide6 hook collects these regardless.
_DROP_DLL = ("qt6qml", "qt6quick", "qt6pdf", "qt6shadertools")


def _keep(entry):
    dest = entry[0].lower().replace(chr(92), "/")
    base = dest.rsplit("/", 1)[-1]
    if base.startswith(_DROP_DLL):
        return False
    if "pyside6/qml/" in dest:
        return False
    if "plugins/qmltooling" in dest:
        return False
    if "pyside6/translations/" in dest:
        return False
    return True


a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name={spec.name!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
)
"""


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

    spec_path = project_root / f"{spec.name}.spec"
    spec_path.write_text(render_spec(project_root, spec), encoding="utf-8")
    print(f"Wrote {spec_path.name} ({len(spec.hidden_imports)} hidden imports)")

    # Build from the generated spec. --clean drops stale caches; --noconfirm
    # overwrites dist/ without prompting.
    cmd = ["pyinstaller", "--noconfirm", "--clean", str(spec_path)]

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
            exclude_modules=get_unused_qt_modules(),
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
            # The tooling reuses foxhole_stockpiles' settings/i18n/models, but
            # --collect-submodules also drags in the runtime-only handlers and
            # services (Google Sheets, screenshot capture, SAV parsing). The
            # tooling never imports those, so drop their heavy dependencies.
            exclude_modules=[
                "google",
                "google_auth_oauthlib",
                "googleapiclient",
                "pywinctl",
                "pynput",
                "fs_sav",
                "httpx",
                "pytesseract",
                *get_unused_qt_modules(),
            ],
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
