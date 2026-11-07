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

Create a JSON file at `<platform config dir>/foxhole-stockpiles/config.json` (on Linux, `~/.config/foxhole-stockpiles/config.json`; on Windows, under `%LOCALAPPDATA%`). A legacy `~/.fs_config` file is moved there automatically:

**Note on Config Versioning:** The configuration includes a `config_version` field (current: **19**). Old configs are automatically migrated when loaded via `ConfigMigrator` - no manual action required. V5 introduced the `output.handlers` array structure (multiple output destinations); later versions added the `sav_processing` section for Foxhole save-file processing; V10 removed the obsolete `api_server` and `api_auth` sections (the FastAPI server was removed in favor of local screenshot capture); V11 removed the `stockpile_types` section (type detection now happens inside the external `fs-ocr` engine, so the aliases had no effect); V12 removed the `notifications` section (the notifier stack was never wired into the scan flow); V13 removed `gui.config_level` (the basic/advanced/developer setting no longer gated anything after OCR/template settings moved to `fs-ocr`/`fs-tools`); V14 reworked the webhook `forward` auth type into `header` (`client_auth_header` → `auth_header`); V15 dropped two dead fields, `scanner.early_exit_threshold` and `sav_processing.emit_all_on_start`; V16 removed the `external_tools` section (`repak`/`umodel`/`uassetgui`) and `database_builder.workers` (the catalog and template database are now built by the external `fs-assets` package, which reads the PAK directly); V17 turned the `aggregate` switch of the `image`/`discord` handlers into `grouping`; V18 moved `grouping` beside the handler of every output, renamed `headline` to `group_name`, and added `public_stockpiles`; V19 dropped `group_name`, since each merge is named after what its stockpiles share.

```json
{
  "config_version": 19,
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
| `confidence_gap` | float | `0.0` | Confidence gap for returning alternative candidates (0.0-1.0). Returns candidates within `(best_confidence - confidence_gap)` range that have the same category, crated status, and mod. Set to 0.0 to disable |
| `screenshots_folder` | string | `""` | Folder to save captured screenshots. When set, each screenshot taken via the capture hotkey is saved here in a per-day subfolder (`YYYY-MM-DD/HHMMSS_<type>_<name>_<resolution>.png`). Empty string disables saving |

> **Removed in config v8:** `custom_model`, `tessdata_path`, `max_ncc_candidates`, `phash_threshold`, and `ncc_tiebreaker_threshold`. **Removed in config v11:** `template_cache_size`, `debug_mode`, and `extract_icons`. **Removed in config v15:** `early_exit_threshold` and `sav_processing.emit_all_on_start`. These no longer have any consumer. Stored values are dropped automatically on migration.

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
| `public_stockpiles` | string | No | Which public stockpiles it receives: `all` (default), `none`, or `non_reservable` |
| `grouping` | string | No | Which stockpiles of a send it receives as one: `none` (default), `all`, `hex` or `location` |

#### Choosing the stockpiles of each output

Each output receives the stockpiles of a send after two steps, in this order. Two outputs can
receive the same send differently, such as a Discord channel with only the reserves, grouped,
and a CSV file with everything.

**1. Public stockpiles** (`public_stockpiles`). Reserve stockpiles always pass.

| Value | Public stockpiles it receives |
|-------|-------------------------------|
| `all` | all of them |
| `none` | none |
| `non_reservable` | only those of structures that cannot hold reserves, such as a bunker or a safe house. In a seaport, a storage depot or an aircraft depot the reserves are what matters |

**2. Grouping** (`grouping`). Each group is received as one stockpile, adding up its items.

| Value | One stockpile for | Named |
|-------|-------------------|-------|
| `none` | each stockpile | |
| `all` | the whole send | `All Stockpiles` |
| `hex` | each hex | the hex, such as `Heartlands` |
| `location` | each place: the stockpiles of one hex at the same coordinates, such as the public and reserve stockpiles of a seaport | the hex and the position, such as `Westgate - X: 0.46 Y: 0.66` |

- A group of a single stockpile is received as it is, with its own name and type.
- Stockpiles from screenshots have no hex or coordinates, so `hex` and `location` leave them alone.
- In a merge, crated and loose items stay apart. If the quantity of an item could not be read
  in one of the stockpiles, its total is unknown (`-1`, shown as `?` in images), because a number
  would hide the stock that could not be read.
- `All Stockpiles` is in the language of the images for the `image` and `discord` outputs,
  and in English for the others. A merge has no type (`Undefined`), and Google Sheets writes
  its name in `stockpile_name`.

If an output fails to deliver a merge, it receives the stockpiles of that merge again with the
next send, so a newer version of one of them replaces the old one instead of adding up twice.

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

The path accepts the [placeholders](#placeholders). Example:
`{timestamp}_{type}_{name}_{resolution}.json` → `2025-01-24_14-30-52_Seaport_MyStockpile_1920x1080.json`

#### Placeholders

The file and image paths and the Discord message accept the same placeholders, replaced with
the values of each stockpile. In the window, the `?` button beside each of those fields lists them.

| Placeholder | Value |
|-------------|-------|
| `{name}` | Name of the stockpile |
| `{type}` | Its type, such as `Seaport` |
| `{hex}` | Its hex, such as `Westgate` |
| `{coords}` | Its position on the map of its hex |
| `{resolution}` | Resolution of the screenshot, such as `1920x1080` |
| `{timestamp}` | Date and time |
| `{year}`, `{month}`, `{day}`, `{hour}`, `{minute}`, `{second}` | Parts of the date and time |
| `{ingame_timestamp}` | Date in the game |
| `{item_count}` | Number of different items |
| `{total_items}` | Sum of the quantities that could be read |

- In a path, the date and time are those of writing it, `{timestamp}` is written as
  `2025-01-24_14-30-52` and `{coords}` as `0.457745,0.664469`. A file with several stockpiles
  is named `multiple_stockpiles` by `{name}`, and its counts add up all of them. Values that
  could leave the folder or that Windows refuses in a name are made safe.
- In a message, the date and time are those of the stockpile, `{timestamp}` is written as
  `2025-01-24 14:30`, `{coords}` as `X: 0.46 Y: 0.66`, and `{type}` is in the language of the images.
- `{stockpile_name}` and `{stockpile_type}` are the former names of `{name}` and `{type}`, and
  still work everywhere.
- An unknown placeholder stays as written.

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

**Image and Discord Handlers** - Draw each stockpile as an image and save it (`"image"`) or
post it to a Discord webhook (`"discord"`). See [Images and Discord](images-and-discord.md).

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

### Database Builder (`database_builder`)

Settings for building the template database (used by the fs-tools GUI, backed by `fs-assets`).

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `catalog_file` | string\|null | `null` | Path to catalog.json file for building the database |
| `target_resolutions` | array[string]\|null | `null` | Resolutions to generate (null = all supported) |

**Example:**
```bash
export FS_DATABASE_BUILDER__CATALOG_FILE=/path/to/catalog.json
export FS_DATABASE_BUILDER__TARGET_RESOLUTIONS='["1080", "1440", "2160"]'
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
| `mode` | string | `"manual"` | `"manual"`: a hotkey scans the file once per press. `"monitor"`: the file is polled for changes |
| `sav_capture_key` | string\|null | `null` | Global hotkey for manual mode (e.g. `"F10"`). Windows only |
| `sav_file_path` | string\|null | `null` | Path to the Foxhole save file (`.sav`) to process |
| `poll_interval` | float | `1.0` | Polling interval in seconds for monitoring mode (0.1–60.0) |

**Example:**
```bash
export FS_SAV_PROCESSING__SAV_FILE_PATH="/path/to/User_MapData.sav"
export FS_SAV_PROCESSING__POLL_INTERVAL=2.0
```

### Clipboard (`clipboard`)

Settings for reading stockpiles copied with the in-game **Copy to Clipboard** button.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `mode` | string | `"manual"` | `"manual"`: a hotkey reads the clipboard once per press. `"monitor"`: the clipboard is polled and each new export is emitted |
| `clip_capture_key` | string\|null | `null` | Global hotkey for manual mode (e.g. `"F11"`). Windows only |
| `poll_interval` | float | `1.0` | Polling interval in seconds for monitor mode (0.1–60.0) |

**Example:**
```bash
export FS_CLIPBOARD__MODE=monitor
export FS_CLIPBOARD__POLL_INTERVAL=2.0
```

## Common Configurations

### Scanner with Webhook Output

```bash
export FS_OUTPUT__HANDLERS='[{"name":"Webhook","format":{"type":"json"},"handler":{"type":"webhook","url":"https://api.example.com/stockpiles","auth_type":"bearer","token":"webhook-token-456"}}]'
```

Or in your config file:
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
2. Configuration file (`config.json`, see above)
3. Default values

Environment variables always override configuration file settings.

## Complete Configuration Reference

### Full Configuration File Example

This example shows all available settings with their default values:

```json
{
  "config_version": 19,
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
        "handler": {"type": "return"},
        "public_stockpiles": "all",
        "grouping": "none"
      }
    ]
  },
  "scanner": {
    "database_path": null,
    "capture_key": null,
    "confidence_gap": 0.0,
    "screenshots_folder": ""
  },
  "database_builder": {
    "catalog_file": null,
    "target_resolutions": null
  },
  "gui": {
    "minimize_to_tray": false,
    "language": "en"
  },
  "sav_processing": {
    "mode": "manual",
    "sav_capture_key": null,
    "sav_file_path": null,
    "poll_interval": 1.0
  },
  "clipboard": {
    "mode": "manual",
    "clip_capture_key": null,
    "poll_interval": 1.0
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
| `FS_SCANNER__CONFIDENCE_GAP` | float | `0.0` | Confidence gap for alternative candidates |
| `FS_SCANNER__SCREENSHOTS_FOLDER` | string | `""` | Folder to save screenshots (empty to disable) |
| **Database Builder** | | | |
| `FS_DATABASE_BUILDER__CATALOG_FILE` | string\|null | `null` | Path to catalog.json |
| `FS_DATABASE_BUILDER__TARGET_RESOLUTIONS` | JSON array\|null | `null` | Resolutions to generate |
| **GUI** | | | |
| `FS_GUI__MINIMIZE_TO_TRAY` | boolean | `false` | Minimize to tray on close |
| `FS_GUI__LANGUAGE` | string | `"en"` | GUI language code |
| **SAV Processing** | | | |
| `FS_SAV_PROCESSING__MODE` | string | `"manual"` | `manual` or `monitor` |
| `FS_SAV_PROCESSING__SAV_CAPTURE_KEY` | string\|null | `null` | Hotkey for manual mode (Windows only) |
| `FS_SAV_PROCESSING__SAV_FILE_PATH` | string\|null | `null` | Path to the Foxhole `.sav` file to process |
| `FS_SAV_PROCESSING__POLL_INTERVAL` | float | `1.0` | Polling interval in seconds for monitoring mode (0.1–60.0) |
| **Clipboard** | | | |
| `FS_CLIPBOARD__MODE` | string | `"manual"` | `manual` or `monitor` |
| `FS_CLIPBOARD__CLIP_CAPTURE_KEY` | string\|null | `null` | Hotkey for manual mode (Windows only) |
| `FS_CLIPBOARD__POLL_INTERVAL` | float | `1.0` | Polling interval in seconds for monitor mode (0.1–60.0) |

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

Handler types: `return`, `file`, `webhook`, `console`, `sheets`, `image`, `discord`
Format types: `json`, `csv`, `tsv`
