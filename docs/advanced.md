# Advanced Usage

For everyday use, see the [main README](../README.md). This guide is for running
the tool with more control: installing from source (required on macOS/Linux), the
command-line interface, building custom OCR databases, and configuration. To work
on the code itself, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## The two executables / packages

The repository ships two installable packages, each exposing a command-line tool:

- **`foxhole_stockpiles`** (the **`fs`** command) — the desktop runtime: CLI, PySide6 GUI, screenshot capture, clipboard, and SAV processing. Packaged as `fs.exe` (a windowed app: the GUI on no arguments, the CLI otherwise).
- **`fs_tools`** (the **`fs-tools`** command) — build-time tooling: item-catalog generation and template-database building/manipulation. Packaged as `fs-tools.exe`.

The heavy lifting is delegated to two external Rust libraries maintained alongside this project and published to PyPI:

- **[`fs-ocr`](https://github.com/xurxogr/fs-ocr)** — the OCR and template-matching engine that scans screenshots.
- **[`fs-sav`](https://github.com/xurxogr/fs-sav)** — the parser for Foxhole `.sav` world files.

## Install and run from source

The prebuilt executables are Windows-only — on macOS/Linux, or to run the latest code, install from source. Requires Python 3.12 or higher.

```bash
git clone https://github.com/xurxogr/foxhole-stockpiles.git
cd foxhole-stockpiles

python -m venv venv
# Windows:        venv\Scripts\activate
# macOS / Linux:  source venv/bin/activate

pip install -e .
# Windows only: screenshot capture and global hotkeys
pip install -e .[capture]
```

This installs the `fs`, `fs-tools`, `fs-gui`, and `fs-tools-gui` commands. A pre-built vanilla template database (`data/fs_vanilla.h5`) and item catalog (`data/catalog.json`) are included, so scanning works immediately.

### Tesseract (only for Chinese OCR)

OCR runs inside the bundled `fs-ocr` engine, which handles quantity detection and every language **except Chinese** with no setup. Install Tesseract only to scan **Chinese** screenshots, along with its Chinese Simplified (`chi_sim`) language data:

```bash
# Windows: install from https://github.com/UB-Mannheim/tesseract/wiki (or `choco install tesseract`),
#          then add chi_sim.traineddata (https://github.com/tesseract-ocr/tessdata)
#          into the tessdata folder (default: C:\Program Files\Tesseract-OCR\tessdata\)

# macOS
brew install tesseract tesseract-lang

# Ubuntu / Debian
sudo apt update && sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

## Command-line interface

Running `fs` with no subcommand launches the GUI. Run `fs <command> --help` for the full options of any command.

### Runtime commands (`fs`)

- **`fs scan --database data/fs_vanilla.h5 --image shot.png`** — scan a screenshot via OCR. Optional `--faction colonials|wardens` to filter. Outputs structured JSON with items, quantities, and metadata.
- **`fs sav [--file MapData.sav | --save-dir DIR] [--once] [--poll-interval N]`** — process a Foxhole `.sav` world file (via `fs-sav`). Watches the file for changes unless `--once`.
- **`fs clip [--once] [--poll-interval N]`** — read a stockpile copied from the in-game UI off the clipboard. Monitors the clipboard continuously unless `--once`.
- **`fs gui`** / **`fs-gui`** — launch the GUI explicitly. (The packaged `fs.exe` is already windowed and opens the GUI when run with no arguments.)

### Tooling commands (`fs-tools`)

- **`fs-tools add-icon`** — add an individual icon to an existing database without a full rebuild.
- **`fs-tools visualize --database db.h5`** — open the database visualizer GUI.
- **`fs-tools debug screenshot.png --database db.h5`** — open the debug image viewer for a screenshot.
- **`fs-tools-gui`** (or `fs-tools` with no subcommand) — the tooling GUI (catalog & database builder).

The item catalog and the icon-template database are built by
[fs-assets](https://pypi.org/project/fs-assets/), installed with fs (CLI `fs-assets`).

## Catalog

The catalog is read straight from the game PAK, without external tools, by
`fs-assets build-catalog` or the **fs-tools GUI** (*Build Catalog*). By default
it keeps the game data and drops audio, visual and engine-internal fields; tick
**Full catalog** in the GUI (or pass `--full`) to keep everything.

```bash
fs-assets build-catalog --pak War-WindowsNoEditor.pak -o catalog.json
```

## Building a custom OCR database (mods or game updates)

> **Recommended: use the GUI.** The **fs-tools GUI** (`fs-tools-gui`, or the GUI from `fs-tools.exe`) has a **Database Builder (Icon Import)** window backed by fs-assets. It checks the mod PAKs against the catalog and asks for the game PAK only when the mod lacks the subtype/crate overlays.

No external tools are needed: fs-assets reads the PAK files directly. You only need your game's PAK (and any mod PAKs) plus a catalog.

CLI (best for scripting / automation):

```bash
# 1. Build the catalog from the game PAK
fs-assets build-catalog --pak War-WindowsNoEditor.pak -o catalog.json

# 2. Add the base game icons (mod name defaults to "vanilla")
fs-assets add-mod --pak War-WindowsNoEditor.pak --catalog catalog.json --db templates.h5

# 3. Optional: add a mod (the game PAK supplies the overlays the mod lacks)
fs-assets check-paks --catalog catalog.json --pak Mod.pak
fs-assets add-mod --pak Mod.pak --vanilla-pak War-WindowsNoEditor.pak --catalog catalog.json --db templates.h5 --mod-name my-mod

# 4. Scan with your custom database
fs scan --database templates.h5 --image shot.png
```

`check-paks` reports how many catalog icons and overlays the PAKs contain. Pass
`--pak` more than once for multi-file mods. Re-adding a mod replaces its
templates; `--resolution 1080,1440` rebuilds only those resolutions.
`fs-assets modify-icon` replaces a single icon from a PNG or `.uasset`.

Per-tool documentation:

- [Add Icon](../fs_tools/commands/add_icon/README.md) — add individual icons to databases

## Configuration

Settings are stored as JSON in the platform config directory (`~/.fs_config`). The schema is **v16** and is migrated to the latest format automatically whenever settings are loaded — no manual migration step.

**Top-level sections:** `logging`, `output`, `scanner`, `database_builder`, `gui`, `sav_processing`, `clipboard`. The capture hotkey lives at `scanner.capture_key` (e.g. `"F9"`).

Any value can be overridden with an environment variable in `FS_<SECTION>__<KEY>` form:

```bash
FS_SCANNER__DATABASE_PATH=/path/to/fs_vanilla.h5
FS_SCANNER__CAPTURE_KEY=F9
```

### Output handlers

A scan produces one stockpile result, fanned out to the handlers configured under `output.handlers`:

- **console** — prints the result to stdout
- **file** — writes JSON, CSV, or TSV to disk
- **webhook** — HTTP POST to a URL (basic, bearer, and header auth; "header" puts the token in a user-chosen header)
- **return** — returns the result to the caller in-process
- **sheets** — appends rows to a Google Sheet

> There is no built-in notification system. To send scans to Discord, use a **webhook** handler pointed at a Discord webhook URL (or any HTTP endpoint).

More configuration guides:

- [Configuration Examples](examples/README.md) — ready-to-use config files
- [Configuration Guide](configuration.md) — environment variables and settings
- [Webhook Integration](webhooks.md) — webhook setup and usage
- [Troubleshooting](troubleshooting.md) — common issues and solutions
