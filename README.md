# Foxhole Stockpiles

[![CI](https://github.com/xurxogr/foxhole-stockpiles/workflows/CI/badge.svg)](https://github.com/xurxogr/foxhole-stockpiles/actions)
[![codecov](https://codecov.io/gh/xurxogr/foxhole-stockpiles/branch/main/graph/badge.svg)](https://codecov.io/gh/xurxogr/foxhole-stockpiles)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A capture-first desktop app that scans Foxhole stockpile screenshots locally and extracts structured stockpile information from game assets.

## Current Implementation Status

This project provides a desktop runtime that captures the live Foxhole game window with a global hotkey, scans it in-process via the external Rust OCR engine, and routes the structured results to your configured outputs. It also ships the tooling pipeline for extracting game assets and building the template databases that power stockpile recognition.

## Why This Tool Exists

Extracting Foxhole stockpile information by hand is slow, error-prone, and difficult to scale.
This tool automates that process by capturing and scanning screenshots locally, converting them into structured, machine-readable data, enabling you to:

- Quickly identify and count stockpile items
- Capture the live game window with a single hotkey, no manual screenshotting
- Output results as JSON/CSV/TSV for automation and tracking
- Route results to files, webhooks, or Google Sheets

The system is designed for flexibility, supporting multiple resolutions and easy database rebuilding when new game content is released.

## Performance & Accuracy

Based on analysis of 1,000+ production scans:

### Detection Accuracy
- **99.99% detection rate** - Only 4 undetected items out of 27,538 scanned
- **97.89% average OCR confidence** - High-quality text recognition
- **Near-perfect matching** - Works reliably across all supported resolutions

### Speed
- **1-2 seconds** per screenshot on modern consumer CPUs (6+ cores)
- **Performance scales with CPU** - More cores = faster processing

### Supported Resolutions
Optimized for all common gaming resolutions with consistent accuracy:
- 1920x1080 (most tested) - 98.32% confidence, 99.99% detection rate
- 1920x1200, 2560x1440, 3840x2160 (4K)
- 1600x1200, 1600x900, 1280x1024

**Note:** Performance varies with CPU speed and available cores. The scanner uses OpenCV and Tesseract (C libraries) which benefit significantly from multi-core processors.

## What It Does

The project provides a comprehensive toolkit for Foxhole stockpile recognition:

**Core Pipeline Tools:**
1. **Asset Extraction** - Extracts icon assets from Foxhole PAK files
2. **Template Generation** - Creates resolution-specific templates with crate overlays
3. **Database Building** - Compiles templates into optimized binary databases
4. **Scanner Tool** - Analyzes screenshots to detect and identify stockpile items with automatic quantity recognition

**Additional Tools:**
5. **Screenshot Capture** - Captures the live Foxhole game window with a global hotkey and scans it in-process
6. **Inspector Tool** - Debugs and validates template databases
7. **GUI Application** - User-friendly graphical interface for configuration and scanning
8. **SAV Processing** - Parses Foxhole `.sav` world files into structured stockpile data
9. **Database Management** - Tools for adding icons and migrating database formats

For technical details on the system design and implementation decisions, see the [Architecture Codemap](docs/CODEMAPS/architecture.md) (and the [Codemap Index](docs/CODEMAPS/INDEX.md) for an overview of all packages).

## Available Command-Line Tools

Commands are split between two binaries: **`fs`** (the runtime — scanning, screenshot capture, GUI, save files) and **`fs-tools`** (build-time asset and database tooling). Running `fs` with no subcommand launches the GUI.

### Runtime commands (`fs`)

#### fs scan
Analyzes Foxhole stockpile screenshots to detect items and quantities using the compiled database. Automatically detects item quantities using OCR with a custom-trained Tesseract model optimized for Foxhole's Renner font.

#### fs sav
Processes Foxhole `.sav` world files (via the `fs-sav` Rust parser) into structured stockpile data.

#### fs gui / fs-gui
Launches the PySide6 graphical user interface for managing configurations, running scans, and capturing the live game window. Provides a user-friendly interface for non-technical users.

### Tooling commands (`fs-tools`)

#### fs-tools build-catalog
Builds catalog.json from Foxhole PAK files by extracting game blueprints, converting them to JSON, and parsing item definitions. Generates the complete item catalog automatically without manual data entry.

#### fs-tools extract-assets
Extracts icon assets from Foxhole PAK files and converts them to PNG format.

#### fs-tools generate-templates
Generates resolution-specific template variants from extracted assets with proper scaling and crate overlays.

#### fs-tools build-db
Compiles processed templates into optimized binary databases for fast runtime loading.

#### fs-tools inspect
Debugging tool for inspecting database contents and testing icon recognition.

#### fs-tools add-icon
Manually adds individual icons to existing template databases without rebuilding the entire database.

#### fs-tools add-mod
Adds all icons from a mod's PAK file(s) to the template database in one command. Runs the complete pipeline: extracting assets, generating templates, and merging into the database.

#### fs-tools-gui
Launches the PySide6 tooling GUI for catalog/database management.

### GUI launch notes

- `fs gui` - Launches GUI via CLI dispatcher
- `fs-gui` - Direct GUI launcher (no console window on Windows, recommended for building standalone executables)

**Configuration Levels:**

The GUI uses a tiered configuration system to avoid overwhelming users with advanced options:

- **Basic** (default): Essential tabs only - Scanner, Output, Logging, and GUI. Suitable for most users.
- **Advanced**: Adds the Stockpile Types, Notifications, and SAV Processing tabs, plus additional fields in existing tabs (debug mode, log file configuration, custom loggers, etc.).
- **Developer**: Same tabs as Advanced, but unlocks the remaining advanced fields for fine-tuning. Only use this if you understand the impact of these settings.

**Stockpile Types Tab (Advanced):**

The Stockpile Types tab allows you to add custom aliases for stockpile type names to handle OCR errors. For example, if OCR sometimes detects "Seaport" as "seapon", you can add "seapon" as an alias. The default translations for all supported languages are already built-in.

Change the configuration level in the GUI tab within the Configuration window.

**Localization:**

The GUI supports multiple languages. Change the interface language in the GUI tab within the Configuration window.

> **Note:** Translations were generated with AI assistance and may contain inaccuracies. If you notice any translation errors or would like to help improve translations for your language, contributions are greatly appreciated!

Supported languages:
- English (en)
- German (de)
- Spanish (es)
- French (fr)
- Portuguese (pt)
- Russian (ru)
- Chinese (zh)

**Contributing Translations:**

Translation files are located in `foxhole_stockpiles/i18n/translations/`. Each language has a JSON file (e.g., `en.json`, `es.json`) containing all translatable strings.

To add or improve translations:
1. Copy `en.json` as a template for a new language
2. Translate all string values (keep the keys unchanged)
3. Update `language_name` and `language_code` at the top of the file
4. Submit a pull request

**Custom Translations (Standalone Executable):**

When using the standalone executable (`fs.exe` or `fs-gui.exe`), you can add or override translations without modifying the application:

1. Create an `i18n/translations/` folder next to the executable
2. Place your custom `.json` translation files there
3. The application will merge your translations with the bundled ones

```
dist/
├── fs.exe
└── i18n/
    └── translations/
        └── en.json      # Override specific keys in English
```

User translations are **merged** with bundled ones - you only need to include the keys you want to override. For example, to fix a single translation:

```json
{
  "common": {
    "cancel": "My Custom Cancel Text"
  }
}
```

This will override just that key while keeping all other translations from the bundled file.

## Requirements

- Python 3.12 or higher
- **Tesseract OCR** - Required for quantity detection from stockpile screenshots
- Custom Tesseract model for Renner font recognition (included in repository)

### For Scanner Only

- **Pre-built template database** (`data/fs_vanilla.h5`) - Included in repository
- **Item catalog** (`data/catalog.json`) - Included in repository

### For Custom Database Building (Optional)

- External tools (Windows-specific):
  - `repak.exe` - For PAK file extraction
  - `umodel.exe` - For asset conversion
- Foxhole game PAK files (from your game installation)
- Mod PAK files (if using custom mods)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/xurxogr/foxhole-stockpiles.git
cd foxhole-stockpiles
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install the Package

```bash
# Install the package (includes the GUI, screenshot capture, and all CLI tools)
pip install -e .

# Install with development dependencies (adds testing, linting, etc.)
pip install -e .[dev]
```

### 4. Install and Configure Tesseract OCR

#### Install Tesseract

**Windows:**
```bash
# Download and install from: https://github.com/UB-Mannheim/tesseract/wiki
# Or using chocolatey:
choco install tesseract
```

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install tesseract-ocr
```

#### Set Up Custom Renner Font Model

The stockpile scanner uses a custom-trained Tesseract model (`renner_numbers.traineddata`) optimized for recognizing quantities in Foxhole's Renner font. **This model is required for accurate quantity detection and is already included in the repository** in the `tessdata/` folder.

The directory structure is:
```
foxhole-stockpiles/
├── tessdata/
│   └── renner_numbers.traineddata  # Already provided - required for quantity detection
└── ...
```

The scanner automatically uses this custom model for quantity detection. For stockpile names, types, and other text detection, the scanner uses standard Tesseract language models.

#### Install Additional Language Support (Optional)

Foxhole supports multiple languages. If you want to detect stockpile information in languages other than English, you need to install the corresponding Tesseract language data files:

**Supported Languages:**
- English (eng) - Included with Tesseract by default
- Portuguese (por)
- French (fra)
- German (deu)
- Russian (rus)
- Chinese Simplified (chi_sim)

**Installation:**

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr-por tesseract-ocr-fra tesseract-ocr-deu \
                 tesseract-ocr-rus tesseract-ocr-chi-sim
```

**macOS:**
```bash
brew install tesseract-lang
```

**Windows:**
- Download language data files from https://github.com/tesseract-ocr/tessdata
- Place `.traineddata` files in your Tesseract installation's `tessdata` folder
  - Default location: `C:\Program Files\Tesseract-OCR\tessdata\`

**Note:** If you only play Foxhole in English, you don't need to install additional language packs. The scanner will work perfectly with just the English model (included by default) and the bundled `renner_numbers` model for quantity detection.

### 5. Set Up Pre-Commit Hooks (Optional, for Development)

```bash
pre-commit install
```

## Usage Workflow

### Quick Start (Using Pre-built Database)

A pre-built template database for vanilla Foxhole items is included in the repository at `data/fs_vanilla.h5`.

Run the scanner:

```bash
fs scan \
  --database data/fs_vanilla.h5 \
  --image your_screenshot.png
```

Optional filters:
```bash
# Filter by faction
fs scan --database data/fs_vanilla.h5 --image screenshot.png --faction colonials
```

The scanner will automatically:
- Detect and identify all items in the stockpile
- Extract quantities using OCR with the custom Renner font model
- Output structured JSON data with items, quantities, and metadata
- Validate mod names against available mods in the database

### Screenshot Capture (Global Hotkey)

The desktop runtime can capture the live Foxhole game window with a configurable global hotkey and scan it in-process — no manual screenshotting or external server required.

1. Set a capture hotkey in **Settings** (or via config at `scanner.capture_key`, e.g. `"F9"`).
2. Launch Foxhole and open a stockpile in-game.
3. Make sure the Foxhole window (titled "War") is the active, non-minimized window. Capture works across multiple monitors.
4. Press the hotkey. The runtime grabs the game window, scans it via the Rust OCR engine, and routes the result to your configured output handlers (console, file, webhook, Google Sheets, etc.).

Window detection uses `pywinctl`, the global hotkey uses `pynput`, and the screen grab uses Pillow's `ImageGrab`.

### Building Custom Database (For Mods or Game Updates)

If you need to include custom mods or rebuild the database for a new game version:

1. **Extract assets from game PAK files:**
```bash
fs-tools extract-assets \
  --catalog data/catalog.json \
  --pak "C:/Program Files (x86)/Steam/steamapps/common/Foxhole/War/Content/Paks/War-WindowsNoEditor.pak" \
  --output raw_assets/
```

2. **Generate resolution-specific templates:**
```bash
fs-tools generate-templates \
  --catalog data/catalog.json \
  --assets raw_assets/ \
  --templates processed_templates/
```

3. **Build optimized binary database:**
```bash
fs-tools build-db \
  --catalog data/catalog.json \
  --templates processed_templates/ \
  --database data/foxhole_templates.h5
```

4. **Scan with your custom database:**
```bash
fs scan \
  --database data/foxhole_templates.h5 \
  --image your_screenshot.png
```

## Packages & Core Dependencies

The repository ships two installable packages:

- **`foxhole_stockpiles`** - the desktop runtime: CLI, PySide6 GUI, screenshot capture, and SAV processing.
- **`fs_tools`** - build-time asset and template-database tooling.

OCR is provided by the external PyPI package **`fs-ocr`** (a Rust engine), and `.sav` parsing by the external **`fs-sav`** (Rust) package.

Core dependencies:

- **Image Processing**: OpenCV (opencv-python), NumPy
- **OCR**: `fs-ocr` (external Rust engine); Tesseract OCR powers quantity detection
- **Screenshot Capture**: `pywinctl` (window detection), `pynput` (global hotkey), Pillow (`ImageGrab`)
- **GUI**: PySide6
- **Data Handling**: Pydantic v2 for validation
- **Development**: Ruff (linting), MyPy (type checking), Pre-commit hooks

## Configuration

Configuration is stored as JSON in the platform config directory (`~/.fs_config`). The schema is **v10** and is migrated to the latest format automatically whenever settings are loaded; no manual migration step is required.

**Top-level sections:**
`external_tools`, `logging`, `output`, `scanner`, `stockpile_types`, `database_builder`, `notifications`, `gui`, `sav_processing`.

The screenshot capture hotkey lives at `scanner.capture_key` (e.g. `"F9"`).

**Environment variable overrides** use the `FS_<SECTION>__<KEY>` format, for example:

```bash
FS_SCANNER__DATABASE_PATH=/path/to/fs_vanilla.h5
FS_SCANNER__CAPTURE_KEY=F9
```

### Output Handlers

A scan produces one stockpile result, which is fanned out to the handlers configured under the `output.handlers` list:

- **console** - prints the result to stdout
- **file** - writes JSON, CSV, or TSV to disk
- **webhook** - HTTP POST to a URL (supports basic, bearer, and forward auth; "forward" passes a client-provided header through)
- **return** - returns the result to the caller in-process
- **sheets** - appends rows to a Google Sheet

For more details, see:
- [Configuration Examples](docs/examples/README.md) - Ready-to-use config files
- [Configuration Guide](docs/configuration.md) - Environment variables and settings
- [Webhook Integration](docs/webhooks.md) - Webhook setup and usage

### Notifications

The runtime includes a notification system that can send alerts to Discord channels when stockpile scans occur or errors are encountered.

**Configuration:**

Add notifications to your `.fs_config` or environment variables:

```json
{
  "notifications": {
    "enabled": true,
    "notifiers": [
      {
        "type": "discord",
        "name": "Main Server",
        "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
        "username": "Stockpile Bot",
        "events": [
          "stockpile.scanned",
          "stockpile.scan_failed"
        ],
        "message_templates": {
          "stockpile.scanned": "📦 STOCKPILE_NAME @ SHARD [TIME] - ITEM_COUNT items (UNMATCHED_ITEMS unknown) - AVG_CONFIDENCE confidence"
        }
      },
      {
        "type": "discord",
        "name": "Admin Channel",
        "webhook_url": "https://discord.com/api/webhooks/ADMIN_WEBHOOK_ID/ADMIN_WEBHOOK_TOKEN",
        "username": "Admin Bot",
        "events": [
          "stockpile.scan_failed"
        ]
      }
    ]
  }
}
```

**Message Templates:**

Customize notification messages using placeholders. If not specified, default templates are used.

Placeholders are replaced with actual values - just use them as-is in your message template.

Available placeholders:
- `STOCKPILE_NAME` - Name of the stockpile
- `STOCKPILE_TYPE` - Type of stockpile (Public, Private, etc.)
- `SHARD` - Shard/server name
- `TIME` - In-game time
- `ITEM_COUNT` - Total number of items
- `MATCHED_ITEMS` - Number of successfully matched items
- `UNMATCHED_ITEMS` - Number of unknown/unmatched items
- `AVG_CONFIDENCE` - Average confidence (formatted as percentage, e.g., "85.6%")
- `DURATION` - Scan duration (formatted as seconds, e.g., "2.34s")
- `RESOLUTION` - Screenshot resolution
- `ERROR` - Error message (for failed events)

Example templates:
```json
"message_templates": {
  "stockpile.scanned": "✅ STOCKPILE_NAME (STOCKPILE_TYPE) - ITEM_COUNT items in DURATION",
  "stockpile.scan_failed": "❌ Scan failed: ERROR",
  "stockpile.scan_started": "🔄 Scanning stockpile..."
}
```

**Note:** Placeholders are case-sensitive and will be replaced exactly as written. Any text not matching a placeholder will remain unchanged, so typos like `{stockpile_name` won't cause errors.

**Environment Variables:**

```bash
# Enable notifications
FS_NOTIFICATIONS__ENABLED=true

# Configure Discord notifiers (JSON array)
FS_NOTIFICATIONS__NOTIFIERS='[{"type":"discord","name":"Main","webhook_url":"https://discord.com/...","events":["stockpile.scanned"]}]'
```

**Available Event Types:**
- `stockpile.scan_started` - Scan has started
- `stockpile.scanned` - Successful scan with item details
- `stockpile.scan_failed` - Scan failed with error message

**Discord Webhook Setup:**
1. In Discord, go to Server Settings → Integrations → Webhooks
2. Click "New Webhook" or "Create Webhook"
3. Set a name and choose the channel
4. Copy the Webhook URL
5. Add the URL to your configuration

**Multiple Notifiers:**
You can configure multiple Discord webhooks to send different events to different channels. For example:
- Main channel: successful scans
- Admin channel: errors
- Dev channel: all events for debugging

## Development

### Code Quality Tools

The project uses several tools to maintain code quality:

```bash
# Run linter
ruff check foxhole_stockpiles/

# Type checking
mypy foxhole_stockpiles/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Building Windows Executable

For Windows users who want a standalone executable, the project includes a build script:

```bash
# Ensure PyInstaller is installed
pip install pyinstaller

# Run the build script
python build_fs.py
```

This creates a single `fs.exe` file in the `dist/` directory that contains all dependencies and can be used without Python installation:

```bash
# Use the executable with the same command syntax
fs.exe scan --database data/fs_vanilla.h5 --image screenshot.png
fs.exe gui
```

The executable is typically 50-80MB and includes all required dependencies except external tools (repak.exe, umodel.exe) which must still be provided separately.

### Testing

The project includes a comprehensive test suite covering all major components:

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=foxhole_stockpiles --cov-report=html

# Run specific test modules
pytest tests/commands/stockpile_scanner/
pytest tests/services/
```

Test coverage includes:
- Command-line tools (asset extraction, template generation, database building, scanner)
- Core services (template matching, OCR processing, stockpile detection)
- Data models and validation
- Screenshot capture and hotkey handling
- Webhook connectors and output handlers

## Documentation

### Command-Line Tools

The main `fs` command (Typer-based) exposes these subcommands — run `fs <command> --help` for options:

- `fs scan` - Analyze stockpile screenshots
- `fs sav` - Process Foxhole save files
- `fs gui` - Launch the graphical user interface

Running `fs` with no subcommand launches the GUI. The installed entry points are `fs`, `fs-tools`, `fs-gui`, and `fs-tools-gui`.

Configuration files are migrated to the latest format automatically whenever settings are loaded; no manual migration step is required.

The asset/database tooling lives in the separate `fs-tools` command, with detailed documentation in each tool's directory:

- [Catalog Builder](fs_tools/commands/catalog_builder/README.md) - Build catalog.json from PAK files
- [Asset Extractor](fs_tools/commands/uasset_extractor/README.md) - Extract icons from PAK files
- [Template Generator](fs_tools/commands/generate_templates/README.md) - Generate resolution-specific templates
- [Database Builder](fs_tools/commands/database_builder/README.md) - Build optimized template databases
- [Inspector](fs_tools/commands/candidate_inspector/README.md) - Debug and validate databases
- [Add Icon](fs_tools/commands/add_icon/README.md) - Add individual icons to databases
- [Add Mod](fs_tools/commands/add_mod/README.md) - Add mod icons to databases

### Guides

- [Configuration Examples](docs/examples/README.md) - Ready-to-use config files
- [Configuration Guide](docs/configuration.md) - Environment variables and settings
- [Webhook Integration](docs/webhooks.md) - Webhook setup and usage
- [Troubleshooting](docs/troubleshooting.md) - Common issues and solutions

## Credits

This project was inspired by the [FIR (Foxhole Item Recognition)](https://github.com/GICodeWarrior/fir) project:
- **catalog.json**: Used FIR's catalog until we developed our own catalog builder
- **Conceptual approach**: Image generation from PAK extraction inspired by FIR

## License

This project is licensed under the MIT License - see the LICENSE file for details.

**Note**: The included `data/catalog.json` and pre-built template database (available in releases) contain data derived from Foxhole game assets, which are property of [Siege Camp](https://www.siegecamp.com/). These files are made available under Fair Use for personal use. Users are responsible for complying with applicable terms of service.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.
