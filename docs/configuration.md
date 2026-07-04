# Configuration Guide

The Foxhole Stockpile Scanner can be configured using environment variables or a configuration file.

## Configuration Methods

### 1. Environment Variables

Environment variables use the prefix `FS_` and nested settings are separated by `__` (format: `FS_<SECTION>__<KEY>`):

```bash
# Scanner settings
export FS_SCANNER__DATABASE_PATH=/path/to/database.h5
export FS_SCANNER__CAPTURE_KEY=F9
export FS_SCANNER__CONFIDENCE_GAP=0.0

# Output handlers (JSON array)
export FS_OUTPUT__HANDLERS='[{"name":"Local Scan","format":{"type":"json"},"handler":{"type":"return"}}]'

# Logging
export FS_LOGGING__LOG_LEVEL=DEBUG
export FS_LOGGING__LOG_FILE=/var/log/foxhole-scanner.log
```

### 2. Configuration File

Create a file at `~/.fs_config` with JSON configuration:

**Note on Config Versioning:** The configuration includes a `config_version` field (current: **15**). Old configs are automatically migrated when loaded via `ConfigMigrator` - no manual action required. V5 introduced the `output.handlers` array structure (multiple output destinations); later versions added the `sav_processing` section for Foxhole save-file processing; V10 removed the obsolete `api_server` and `api_auth` sections (the FastAPI server was removed in favor of local screenshot capture); V11 removed the `stockpile_types` section (type detection now happens inside the external `fs-ocr` engine, so the aliases had no effect); V12 removed the `notifications` section (the notifier stack was never wired into the scan flow); V13 removed `gui.config_level` (the basic/advanced/developer setting no longer gated anything after OCR/template settings moved to `fs-ocr`/`fs-tools`); V14 reworked the webhook `forward` auth type into `header` (`client_auth_header` → `auth_header`); V15 dropped two dead fields, `scanner.early_exit_threshold` and `sav_processing.emit_all_on_start`.

```json
{
  "config_version": 11,
  "scanner": {
    "database_path": "/path/to/database.h5",
    "capture_key": "F9"
  },
  "output": {
    "handlers": [
      {
        "name": "Local Scan",
        "format": {"type": "json"},
        "handler": {"type": "return"}
      }
    ]
  },
  "logging": {
    "log_level": "INFO",
    "log_format": "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "rotate_logs": false,
    "log_file": null,
    "loggers": {}
  }
}
```

## Configuration Sections

### Scanner (`scanner`)

Settings for the stockpile scanner.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `database_path` | string | `null` | Path to the template database file |
| `capture_key` | string\|null | `null` | Global hotkey that captures the Foxhole window and scans it (e.g. `"F9"`). The captured window title is hardcoded to `"War"`. Set to `null` (or leave unset) to disable capture |
| `early_exit_threshold` | float | `0.0` | Early exit threshold for icon matching (0.0-1.0), used by the `fs-tools` candidate inspector. Set to 0.0 to disable early exit |
| `confidence_gap` | float | `0.0` | Confidence gap for returning alternative candidates (0.0-1.0). Returns candidates within `(best_confidence - confidence_gap)` range that have the same category, crated status, and mod. Set to 0.0 to disable |
| `screenshots_folder` | string | `""` | Folder to save captured screenshots. When set, each screenshot taken via the capture hotkey is saved here in a per-day subfolder (`YYYY-MM-DD/HHMMSS_<type>_<name>_<resolution>.png`). Empty string disables saving |

> **Removed in config v8:** `custom_model`, `tessdata_path`, `max_ncc_candidates`, `phash_threshold`, and `ncc_tiebreaker_threshold`. **Removed in config v11:** `template_cache_size`, `debug_mode`, and `extract_icons` — these old in-repo-engine knobs have no remaining consumer. Stored values are dropped automatically on migration.

### Output (`output`)

Controls how scanner results are formatted and where they are sent. The output system supports multiple handlers, allowing results to be sent to different destinations simultaneously.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `handlers` | array | `[]` | List of output handler configurations |

#### Handler Configuration (`output.handlers[]`)

Each handler in the array has the following structure:

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `name` | string | Yes | Friendly name for this handler (e.g., "Local Scan", "File Backup") |
| `format` | object | Yes | Format settings for serialization |
| `handler` | object | Yes | Handler-specific settings |

#### Format Settings (`output.handlers[].format`)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `type` | string | `"json"` | Data serialization format: `"json"`, `"csv"`, or `"tsv"` |

For CSV/TSV formats, additional settings are available:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `fields` | array | all fields | List of fields to include in output |
| `include_header` | boolean | `true` | Whether to include a header row |

#### Handler Types (`output.handlers[].handler`)

**Return Handler** - Returns the result dict to the caller (used by the CLI / local scan):
```json
{"type": "return"}
```

**File Handler** - Saves results to a file:
| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `type` | string | Yes | Must be `"file"` |
| `path` | string | Yes | File path with optional placeholders |

Supported placeholders for file path:
- `{timestamp}` - Full timestamp (e.g., 2025-01-24_14-30-52)
- `{year}`, `{month}`, `{day}` - Date components (e.g., 2025, 01, 24)
- `{hour}`, `{minute}`, `{second}` - Time components (e.g., 14, 30, 52)
- `{stockpile_type}` - Stockpile type (e.g., Seaport, Storage Depot)
- `{stockpile_name}` - Name of the stockpile
- `{resolution}` - Screen resolution (e.g., 1920x1080)

Example: `{timestamp}_{stockpile_type}_{stockpile_name}_{resolution}.json` → `2025-01-24_14-30-52_Seaport_MyStockpile_1920x1080.json`

**Webhook Handler** - POSTs results to a URL:
| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `type` | string | Yes | Must be `"webhook"` |
| `url` | string | Yes | Webhook URL |
| `auth_type` | string\|null | No | Auth method: `"basic"`, `"bearer"`, `"header"`, or `null` |
| `token` | string\|null | No | Auth token (required for `"basic"`, `"bearer"`, or `"header"`) |
| `auth_header` | string\|null | No | Header name to place the token in (required for `"header"`) |

**Console Handler** - Prints results to console:
```json
{"type": "console"}
```

**Google Sheets Handler** - Appends results to a Google Sheet:
| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `type` | string | Yes | Must be `"sheets"` |
| `creds_path` | string | Yes | Path to the Google service-account credentials JSON file |
| `spreadsheet_url` | string | Yes | URL of the target spreadsheet |
| `sheet_id` | string\|null | No | Worksheet/tab ID within the spreadsheet |
| `start_cell` | string\|null | No | Anchor cell where writing begins (e.g. `"A1"`) |
| `row_format` | object\|null | No | Row layout settings controlling how values are written |

#### Example: Multiple Handlers

```json
{
  "output": {
    "handlers": [
      {
        "name": "Local Scan",
        "format": {"type": "json"},
        "handler": {"type": "return"}
      },
      {
        "name": "File Backup",
        "format": {"type": "json"},
        "handler": {"type": "file", "path": "backups/{year}-{month}-{day}/stockpile_{timestamp}.json"}
      },
      {
        "name": "Discord Webhook",
        "format": {"type": "json"},
        "handler": {
          "type": "webhook",
          "url": "https://api.example.com/stockpiles",
          "auth_type": "bearer",
          "token": "your-token"
        }
      }
    ]
  }
}
```

See [Webhooks](webhooks.md) for webhook configuration details.

### Logging (`logging`)

Configure application logging behavior.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `log_level` | string | `"INFO"` | Global log level: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` |
| `log_format` | string | `"[%(asctime)s] %(levelname)s..."` | Python logging format string |
| `date_format` | string | `"%Y-%m-%d %H:%M:%S"` | Date format for log messages |
| `rotate_logs` | boolean | `false` | Enable daily log rotation |
| `log_file` | string\|null | `null` | Path to log file, or `null` for console only |
| `loggers` | object | `{}` | Per-logger level overrides (e.g., `{"foxhole_stockpiles": "DEBUG"}`) |

### External Tools (`external_tools`)

Paths to external tools used by database and catalog builders.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `repak` | string\|null | `null` | Path to repak executable for extracting PAK files |
| `umodel` | string\|null | `null` | Path to umodel executable for converting UAsset files to PNG |
| `uassetgui` | string\|null | `null` | Path to UAssetGUI executable for converting UAsset files to JSON |

**Example:**
```bash
export FS_EXTERNAL_TOOLS__REPAK=/path/to/repak
export FS_EXTERNAL_TOOLS__UMODEL=/path/to/umodel.exe
export FS_EXTERNAL_TOOLS__UASSETGUI=/path/to/UAssetGUI.exe
```

### Database Builder (`database_builder`)

Settings for building the template database.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `catalog_file` | string\|null | `null` | Path to catalog.json file for building the database |
| `target_resolutions` | array[string]\|null | `null` | Resolutions to generate (null = all supported) |
| `workers` | integer\|null | `null` | Worker processes for building (null = auto-detect CPU count) |

**Example:**
```bash
export FS_DATABASE_BUILDER__CATALOG_FILE=/path/to/catalog.json
export FS_DATABASE_BUILDER__TARGET_RESOLUTIONS='["1080", "1440", "2160"]'
export FS_DATABASE_BUILDER__WORKERS=4
```

### GUI (`gui`)

Settings for the graphical user interface.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `minimize_to_tray` | boolean | `false` | Minimize to system tray instead of quitting |
| `language` | string | `"en"` | Language code for the GUI (e.g., `"en"`, `"es"`, `"de"`) |

**Example:**
```bash
export FS_GUI__MINIMIZE_TO_TRAY=true
export FS_GUI__LANGUAGE=es
```

### SAV Processing (`sav_processing`)

Settings for processing Foxhole save files (`.sav`) via the `fs sav` command (backed by the `fs-sav` Rust parser).

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `sav_file_path` | string\|null | `null` | Path to the Foxhole save file (`.sav`) to process |
| `poll_interval` | float | `1.0` | Polling interval in seconds for monitoring mode (0.1–60.0) |
| `emit_all_on_start` | boolean | `true` | Emit all stockpiles on first read (single-scan mode) |

**Example:**
```bash
export FS_SAV_PROCESSING__SAV_FILE_PATH="/path/to/User_MapData.sav"
export FS_SAV_PROCESSING__POLL_INTERVAL=2.0
export FS_SAV_PROCESSING__EMIT_ALL_ON_START=true
```

## Common Configurations

### Scanner with Webhook Output

```bash
export FS_OUTPUT__HANDLERS='[{"name":"Webhook","format":{"type":"json"},"handler":{"type":"webhook","url":"https://api.example.com/stockpiles","auth_type":"bearer","token":"webhook-token-456"}}]'
```

Or in your `.fs_config`:
```json
{
  "output": {
    "handlers": [
      {
        "name": "Webhook",
        "format": {"type": "json"},
        "handler": {
          "type": "webhook",
          "url": "https://api.example.com/stockpiles",
          "auth_type": "bearer",
          "token": "webhook-token-456"
        }
      }
    ]
  }
}
```

### Debug Mode with File Logging

```bash
export FS_LOGGING__LOG_LEVEL=DEBUG
export FS_LOGGING__LOG_FILE=/var/log/foxhole-scanner.log
```

### Save Screenshots for Analysis

```bash
# Save all processed screenshots to a folder
export FS_SCANNER__SCREENSHOTS_FOLDER=screenshots

# Screenshots will be organized in daily subfolders:
# screenshots/2025-10-05/2025-10-05_14-30-45_Storage_Depot_My_Logi_1920x1080.png
```

### Capture-and-Scan Hotkey

```bash
# Press F9 to capture the Foxhole "War" window and scan it
export FS_SCANNER__CAPTURE_KEY=F9
```

## Configuration Priority

Settings are resolved in this order (highest to lowest priority):

1. Environment variables (`FS_*`)
2. Configuration file (`~/.fs_config`)
3. Default values

Environment variables always override configuration file settings.

## Complete Configuration Reference

### Full `.fs_config` Example

This example shows all available settings with their default values:

```json
{
  "config_version": 11,
  "logging": {
    "loggers": {},
    "log_level": "INFO",
    "log_format": "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "rotate_logs": false,
    "log_file": null
  },
  "output": {
    "handlers": [
      {
        "name": "Local Scan",
        "format": {"type": "json"},
        "handler": {"type": "return"}
      }
    ]
  },
  "scanner": {
    "database_path": null,
    "capture_key": null,
    "early_exit_threshold": 0.0,
    "confidence_gap": 0.0
  },
  "external_tools": {
    "repak": null,
    "umodel": null,
    "uassetgui": null
  },
  "database_builder": {
    "catalog_file": null,
    "target_resolutions": null,
    "workers": null
  },
  "gui": {
    "minimize_to_tray": false,
    "language": "en"
  },
  "sav_processing": {
    "sav_file_path": null,
    "poll_interval": 1.0,
    "emit_all_on_start": true
  }
}
```

### All Environment Variables

This table lists all available environment variables with their default values:

| Environment Variable | Type | Default Value | Description |
|---------------------|------|---------------|-------------|
| **Logging** | | | |
| `FS_LOGGING__LOGGERS` | JSON object | `{}` | Per-logger level overrides (see special syntax below) |
| `FS_LOGGING__LOGGERS__<LOGGER_NAME>` | string | N/A | Logger-specific level (e.g., `__foxhole_stockpiles`, `__httpx`) |
| `FS_LOGGING__LOG_LEVEL` | string | `"INFO"` | Global log level |
| `FS_LOGGING__LOG_FORMAT` | string | `"[%(asctime)s] %(levelname)s [%(name)s] %(message)s"` | Log format string |
| `FS_LOGGING__DATE_FORMAT` | string | `"%Y-%m-%d %H:%M:%S"` | Date format |
| `FS_LOGGING__ROTATE_LOGS` | boolean | `false` | Enable log rotation |
| `FS_LOGGING__LOG_FILE` | string\|null | `null` | Log file path |
| **Output** | | | |
| `FS_OUTPUT__HANDLERS` | JSON array | `[]` | List of output handler configurations (see examples below) |
| **Scanner** | | | |
| `FS_SCANNER__DATABASE_PATH` | string | `null` | Template database path |
| `FS_SCANNER__CAPTURE_KEY` | string\|null | `null` | Hotkey to capture the Foxhole "War" window and scan it (e.g. `F9`); `null` disables capture |
| `FS_SCANNER__EARLY_EXIT_THRESHOLD` | float | `0.0` | Early exit threshold (used by `fs-tools`) |
| `FS_SCANNER__CONFIDENCE_GAP` | float | `0.0` | Confidence gap for alternative candidates |
| `FS_SCANNER__SCREENSHOTS_FOLDER` | string | `""` | Folder to save screenshots (empty to disable) |
| **External Tools** | | | |
| `FS_EXTERNAL_TOOLS__REPAK` | string\|null | `null` | Path to repak executable |
| `FS_EXTERNAL_TOOLS__UMODEL` | string\|null | `null` | Path to umodel executable |
| `FS_EXTERNAL_TOOLS__UASSETGUI` | string\|null | `null` | Path to UAssetGUI executable |
| **Database Builder** | | | |
| `FS_DATABASE_BUILDER__CATALOG_FILE` | string\|null | `null` | Path to catalog.json |
| `FS_DATABASE_BUILDER__TARGET_RESOLUTIONS` | JSON array\|null | `null` | Resolutions to generate |
| `FS_DATABASE_BUILDER__WORKERS` | integer\|null | `null` | Worker processes (null = auto) |
| **GUI** | | | |
| `FS_GUI__MINIMIZE_TO_TRAY` | boolean | `false` | Minimize to tray on close |
| `FS_GUI__LANGUAGE` | string | `"en"` | GUI language code |
| **SAV Processing** | | | |
| `FS_SAV_PROCESSING__SAV_FILE_PATH` | string\|null | `null` | Path to the Foxhole `.sav` file to process |
| `FS_SAV_PROCESSING__POLL_INTERVAL` | float | `1.0` | Polling interval in seconds for monitoring mode (0.1–60.0) |
| `FS_SAV_PROCESSING__EMIT_ALL_ON_START` | boolean | `true` | Emit all stockpiles on first read |

**Note:** For JSON values (arrays/objects), use proper JSON syntax in the environment variable:
```bash
export FS_DATABASE_BUILDER__TARGET_RESOLUTIONS='["1080","1440","2160"]'
```

#### Per-Logger Level Configuration

The `loggers` setting has special syntax for environment variables. You can set logger-specific levels in two ways:

**Method 1: Individual logger variables (recommended)**
```bash
export FS_LOGGING__LOGGERS__foxhole_stockpiles=DEBUG
export FS_LOGGING__LOGGERS__httpx=ERROR
```

**Method 2: JSON object**
```bash
export FS_LOGGING__LOGGERS='{"foxhole_stockpiles":"DEBUG","httpx":"ERROR"}'
```

**In config file:**
```json
{
  "logging": {
    "loggers": {
      "foxhole_stockpiles": "DEBUG",
      "httpx": "ERROR"
    }
  }
}
```

Valid log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

When a logger-specific level is set, it overrides the global `log_level` for that logger only.

#### Output Handlers Configuration

The `handlers` setting is a JSON array. Configure via environment variable:

**Single handler (return result dict to the caller):**
```bash
export FS_OUTPUT__HANDLERS='[{"name":"Local Scan","format":{"type":"json"},"handler":{"type":"return"}}]'
```

**File output:**
```bash
export FS_OUTPUT__HANDLERS='[{"name":"File Output","format":{"type":"json"},"handler":{"type":"file","path":"output.json"}}]'
```

**Webhook with authentication:**
```bash
export FS_OUTPUT__HANDLERS='[{"name":"Webhook","format":{"type":"json"},"handler":{"type":"webhook","url":"https://api.example.com/stockpiles","auth_type":"bearer","token":"your-token"}}]'
```

**Multiple handlers (results sent to all destinations):**
```bash
export FS_OUTPUT__HANDLERS='[
  {"name":"Local Scan","format":{"type":"json"},"handler":{"type":"return"}},
  {"name":"Backup","format":{"type":"json"},"handler":{"type":"file","path":"backup.json"}}
]'
```

Handler types: `return`, `file`, `webhook`, `console`, `sheets`
Format types: `json`, `csv`, `tsv`
