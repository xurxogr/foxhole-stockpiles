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

- **`fs-tools build-catalog`** — build `catalog.json` from Foxhole PAK files (extracts blueprints, converts to JSON, parses item definitions).
- **`fs-tools extract-assets`** — extract icon assets from PAK files and convert them to PNG.
- **`fs-tools generate-templates`** — generate resolution-specific template variants from extracted assets.
- **`fs-tools build-db`** — compile templates into an optimized `.h5` database.
- **`fs-tools add-icon`** — add an individual icon to an existing database without a full rebuild.
- **`fs-tools add-mod`** — run the full extract → templates → merge pipeline for a mod's PAK file(s).
- **`fs-tools-gui`** — the tooling GUI (catalog & database builder).

## Catalog rules (output variants)

The **catalog builder GUI** (`fs-tools-gui` → *Build Catalog*) can project the
generated catalog through a **field rule set** before writing it, so you can
produce a much smaller catalog that still drives the app. Pick a preset from the
dropdown, or open **Edit rules…** to customise it:

- **Full** — keep every field (the default; identical to the `build-catalog` CLI output).
- **FS** — keep only the fields the app actually reads (clipboard conversion +
  template-database build). This is roughly 9% of the full size and is
  behaviourally identical for those two consumers.

Rules are an ordered list of **include/exclude** entries over dotted field
paths, evaluated **last-match-wins** (default: keep). Patterns support segment
globs — `*` matches one path segment, `**` matches one or more — and an ancestor
pattern keeps the whole subtree:

```
exclude **                                # drop everything, then re-add:
include CodeName
include DisplayNameLocales                # keeps the whole locales subtree
include ItemProfileData.bIsCratable       # keeps just this nested field
```

Editing a preset flips it to **Custom**; switching back to a preset warns before
discarding custom edits. Rule sets can be **imported/exported as JSON** (they are
not stored in the app config). If a rule set would drop a field the app needs,
the editor and the build step show a **warning** listing the missing fields.

The CLI `build-catalog` always writes the Full catalog; rules are a GUI feature.

## Building a custom OCR database (mods or game updates)

> **Recommended: use the GUI.** The **fs-tools GUI** (`fs-tools-gui`, or the GUI from `fs-tools.exe`) has a **Database Builder** that runs the whole pipeline — extract → generate templates → build — with validation, progress, and sensible defaults. It is much easier and less error-prone than chaining the CLI commands by hand.

You'll need the external tools `repak.exe` (PAK extraction) and `umodel.exe` (asset conversion), plus your game's PAK files (and any mod PAKs).

Manual CLI pipeline (best for scripting / automation):

```bash
# 1. Extract assets from game PAK files
fs-tools extract-assets \
  --catalog data/catalog.json \
  --pak "C:/Program Files (x86)/Steam/steamapps/common/Foxhole/War/Content/Paks/War-WindowsNoEditor.pak" \
  --output raw_assets/

# 2. Generate resolution-specific templates
fs-tools generate-templates \
  --catalog data/catalog.json \
  --assets raw_assets/ \
  --templates processed_templates/

# 3. Build the optimized binary database
fs-tools build-db \
  --catalog data/catalog.json \
  --templates processed_templates/ \
  --database data/foxhole_templates.h5

# 4. Scan with your custom database
fs scan --database data/foxhole_templates.h5 --image shot.png
```

Per-tool documentation:

- [Catalog Builder](../fs_tools/commands/catalog_builder/README.md) — build `catalog.json` from PAK files
- [Asset Extractor](../fs_tools/commands/uasset_extractor/README.md) — extract icons from PAK files
- [Template Generator](../fs_tools/commands/generate_templates/README.md) — generate resolution-specific templates
- [Database Builder](../fs_tools/commands/database_builder/README.md) — build optimized template databases
- [Add Icon](../fs_tools/commands/add_icon/README.md) — add individual icons to databases
- [Add Mod](../fs_tools/commands/add_mod/README.md) — add mod icons to databases

## Configuration

Settings are stored as JSON in the platform config directory (`~/.fs_config`). The schema is **v13** and is migrated to the latest format automatically whenever settings are loaded — no manual migration step.

**Top-level sections:** `external_tools`, `logging`, `output`, `scanner`, `database_builder`, `gui`, `sav_processing`. The capture hotkey lives at `scanner.capture_key` (e.g. `"F9"`).

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
