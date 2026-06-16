# Configuration Guide

The Foxhole Stockpile Scanner can be configured using environment variables or a configuration file.

## Configuration Methods

### 1. Environment Variables

Environment variables use the prefix `FS_` and nested settings are separated by `__`:

```bash
# API Authentication
export FS_API_AUTH__AUTH_TYPE=bearer
export FS_API_AUTH__AUTH_TOKEN=your-secret-token

# Scanner settings
export FS_SCANNER__DATABASE_PATH=/path/to/database.h5
export FS_SCANNER__TEMPLATE_CACHE_SIZE=16

# Output handlers (JSON array)
export FS_OUTPUT__HANDLERS='[{"name":"API Response","format":{"type":"json"},"handler":{"type":"return"}}]'

# Logging
export FS_LOGGING__LOG_LEVEL=DEBUG
export FS_LOGGING__LOG_FILE=/var/log/foxhole-scanner.log
```

### 2. Configuration File

Create a file at `~/.fs_config` with JSON configuration:

**Note on Config Versioning:** The configuration includes a `config_version` field (current: **9**). Old configs are automatically migrated when loaded via `ConfigMigrator` - no manual action required. V5 introduced the `output.handlers` array structure (multiple output destinations); later versions added the `sav_processing` section for Foxhole save-file processing; V9 removed the obsolete `api_server.web_icon_mod` field.

```json
{
  "config_version": 9,
  "api_server": {
    "cors_allow_origins": [],
    "enable_memory_monitoring": false,
    "auto_trim_memory": true
  },
  "api_auth": {
    "auth_type": "bearer",
    "auth_token": "your-secret-token"
  },
  "scanner": {
    "database_path": "/path/to/database.h5",
    "screenshots_folder": ""
  },
  "output": {
    "handlers": [
      {
        "name": "API Response",
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

### API Server (`api_server`)

Settings for the API server.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `cors_allow_origins` | array[string] | `[]` | List of allowed CORS origins. Empty list allows no cross-origin requests. Use `["*"]` to allow all origins (not recommended for production) |
| `host` | string | `"127.0.0.1"` | Server bind host address |
| `port` | integer | `8000` | Server bind port (1-65535) |
| `workers` | integer | `1` | Number of worker processes |
| `reload` | boolean | `false` | Enable auto-reload on code changes (development only) |
| `log_level` | string | `"info"` | Server log level (`"debug"`, `"info"`, `"warning"`, `"error"`) |
| `enable_memory_monitoring` | boolean | `false` | Enable memory monitoring to track memory usage per request and expose `/memory/*` endpoints |
| `auto_trim_memory` | boolean | `true` | Automatically call `malloc_trim()` after scan requests to release freed memory back to OS |

**Examples:**
```bash
# Allow all origins (development)
export FS_API_SERVER__CORS_ALLOW_ORIGINS='["*"]'

# Allow specific origins (production)
export FS_API_SERVER__CORS_ALLOW_ORIGINS='["https://yourdomain.com","https://app.yourdomain.com"]'

# Production server configuration
export FS_API_SERVER__HOST=0.0.0.0
export FS_API_SERVER__PORT=8080
export FS_API_SERVER__WORKERS=4
```

### API Authentication (`api_auth`)

Controls authentication for the API server endpoints.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `auth_type` | string\|null | `null` | Authentication method. Valid values: `"basic"`, `"bearer"`, or `null` to disable |
| `auth_token` | string\|null | `null` | Authentication token/credentials |

**Note:** Both `auth_type` and `auth_token` must be set together or both be `null`. The `"forward"` auth type is not supported for API authentication.

See [API Authentication](api-authentication.md) for detailed examples.

### Scanner (`scanner`)

Settings for the stockpile scanner.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `database_path` | string | `null` | Path to the template database file |
| `template_cache_size` | integer | `16` | Max resolution databases to cache in memory (0=no cache, 16=all resolutions) |
| `early_exit_threshold` | float | `0.0` | Early exit threshold for icon matching (0.0-1.0). Set to 0.0 to disable early exit |
| `confidence_gap` | float | `0.0` | Confidence gap for returning alternative candidates (0.0-1.0). Returns candidates within `(best_confidence - confidence_gap)` range that have the same category, crated status, and mod. Set to 0.0 to disable |
| `debug_mode` | boolean | `false` | Enable debug mode to save debug images |
| `extract_icons` | boolean | `false` | Extract detected icons to 'icons' folder for debugging |
| `screenshots_folder` | string | `""` | Folder to save screenshots before processing. Empty string disables saving. Screenshots are saved in daily subfolders with format: `Date_HourWithSeconds_StorageType_Name_Resolution.png` |

> **Removed in config v8:** `custom_model`, `tessdata_path`, `max_ncc_candidates`, `phash_threshold`, and `ncc_tiebreaker_threshold` are no longer user-configurable — the OCR model name, tessdata path, and icon-matching thresholds now use fixed defaults. Stored values are dropped automatically on migration.

### Output (`output`)

Controls how scanner results are formatted and where they are sent. The output system supports multiple handlers, allowing results to be sent to different destinations simultaneously.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `handlers` | array | `[]` | List of output handler configurations |

#### Handler Configuration (`output.handlers[]`)

Each handler in the array has the following structure:

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `name` | string | Yes | Friendly name for this handler (e.g., "API Response", "File Backup") |
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

**Return Handler** - Returns data to the API caller:
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
| `auth_type` | string\|null | No | Auth method: `"basic"`, `"bearer"`, `"forward"`, or `null` |
| `token` | string\|null | No | Auth token (required for `"basic"` or `"bearer"`) |
| `client_auth_header` | string\|null | No | Header to forward (required for `"forward"`) |

**Console Handler** - Prints results to console:
```json
{"type": "console"}
```

#### Example: Multiple Handlers

```json
{
  "output": {
    "handlers": [
      {
        "name": "API Response",
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

### Stockpile Types (`stockpile_types`)

Configure additional aliases for stockpile type recognition. The standard translations (English, French, German, Portuguese, Russian, Chinese) are hardcoded in the classifier. These settings allow adding **extra aliases** for OCR misreads or variations.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `encampment` | array[string] | `[]` | Additional aliases for Encampment |
| `keep` | array[string] | `[]` | Additional aliases for Keep |
| `safe_house` | array[string] | `[]` | Additional aliases for Safe House |
| `relic_base` | array[string] | `[]` | Additional aliases for Relic Base |
| `bunker_base` | array[string] | `[]` | Additional aliases for Bunker Base |
| `border_base` | array[string] | `[]` | Additional aliases for Border Base |
| `town_base` | array[string] | `[]` | Additional aliases for Town Base |
| `underground_fortress` | array[string] | `[]` | Additional aliases for Underground Fortress |
| `bms_longhook` | array[string] | `[]` | Additional aliases for BMS - Longhook |
| `bms_bluefin` | array[string] | `[]` | Additional aliases for BMS - Bluefin |
| `storage_depot` | array[string] | `[]` | Additional aliases for Storage Depot |
| `seaport` | array[string] | `[]` | Additional aliases for Seaport |
| `aircraft_depot` | array[string] | `[]` | Additional aliases for Aircraft Depot |

**Note:** Use these settings to handle OCR misreads. For example, if OCR detects "Seaport" as "seapon", add `["seapon"]` to the `seaport` setting.

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

### Notifications (`notifications`)

Settings for the notifications system (e.g., Discord webhooks).

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable or disable notifications |
| `notifiers` | array | `[]` | List of notifier configurations |

#### Discord Notifier Configuration (`notifications.notifiers[]`)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `type` | string | `"discord"` | Notifier type (currently only `"discord"` supported) |
| `name` | string | `"Discord"` | Human-readable name for this notifier |
| `webhook_url` | string | Required | Discord webhook URL |
| `username` | string\|null | `"Foxhole Stockpiles"` | Custom username for webhook messages |
| `events` | array[string] | `["stockpile.scanned", "stockpile.scan_failed"]` | Event types to send |
| `message_templates` | object | `{}` | Custom message templates per event type |

**Available events:**
- `stockpile.scanned` - Stockpile scan completed successfully
- `stockpile.scan_failed` - Stockpile scan failed
- `stockpile.scan_started` - Stockpile scan started
- `server.started` - API server started
- `server.stopped` - API server stopped

**Message template placeholders:**
`STOCKPILE_NAME`, `STOCKPILE_TYPE`, `SHARD`, `TIME`, `ITEM_COUNT`, `MATCHED_ITEMS`, `UNMATCHED_ITEMS`, `AVG_CONFIDENCE`, `DURATION`, `RESOLUTION`, `ERROR`

**Example:**
```json
{
  "notifications": {
    "enabled": true,
    "notifiers": [
      {
        "type": "discord",
        "name": "Main Server",
        "webhook_url": "https://discord.com/api/webhooks/123/abc",
        "username": "Stockpile Bot",
        "events": ["stockpile.scanned", "stockpile.scan_failed"],
        "message_templates": {
          "stockpile.scanned": "📦 STOCKPILE_NAME - ITEM_COUNT items (DURATION)"
        }
      }
    ]
  }
}
```

### GUI (`gui`)

Settings for the graphical user interface.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `config_level` | string | `"basic"` | Configuration level: `"basic"`, `"advanced"`, or `"developer"` |
| `minimize_to_tray` | boolean | `false` | Minimize to system tray instead of quitting |
| `language` | string | `"en"` | Language code for the GUI (e.g., `"en"`, `"es"`, `"de"`) |

**Configuration levels:**
- `basic` - Essential tabs only (recommended for most users)
- `advanced` - Adds Stockpile Types, Notifications, and SAV Processing tabs plus extra fields
- `developer` - Same tabs as advanced, unlocking the remaining advanced fields for fine-tuning

**Example:**
```bash
export FS_GUI__CONFIG_LEVEL=advanced
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

### API Server with Bearer Authentication

```bash
export FS_API_AUTH__AUTH_TYPE=bearer
export FS_API_AUTH__AUTH_TOKEN=my-secret-token-123
```

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
export FS_SCANNER__DEBUG_MODE=true
```

### Save Screenshots for Analysis

```bash
# Save all processed screenshots to a folder
export FS_SCANNER__SCREENSHOTS_FOLDER=screenshots

# Screenshots will be organized in daily subfolders:
# screenshots/2025-10-05/2025-10-05_14-30-45_Storage_Depot_My_Logi_1920x1080.png
```

### Production API Server

```json
{
  "config_version": 9,
  "api_server": {
    "cors_allow_origins": ["https://myapp.com", "https://app.myapp.com"],
    "enable_memory_monitoring": false,
    "auto_trim_memory": true
  },
  "api_auth": {
    "auth_type": "bearer",
    "auth_token": "production-token"
  },
  "logging": {
    "log_level": "INFO",
    "log_file": "/var/log/foxhole-api.log",
    "rotate_logs": true
  },
  "scanner": {
    "database_path": "/opt/foxhole/templates.h5"
  },
  "output": {
    "handlers": [
      {
        "name": "API Response",
        "format": {"type": "json"},
        "handler": {"type": "return"}
      },
      {
        "name": "Webhook",
        "format": {"type": "json"},
        "handler": {
          "type": "webhook",
          "url": "https://api.myapp.com/stockpiles",
          "auth_type": "bearer",
          "token": "internal-webhook-secret"
        }
      }
    ]
  }
}
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
  "config_version": 9,
  "api_server": {
    "cors_allow_origins": [],
    "host": "127.0.0.1",
    "port": 8000,
    "workers": 1,
    "reload": false,
    "log_level": "info",
    "enable_memory_monitoring": false,
    "auto_trim_memory": true
  },
  "api_auth": {
    "auth_type": null,
    "auth_token": null
  },
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
        "name": "API Response",
        "format": {"type": "json"},
        "handler": {"type": "return"}
      }
    ]
  },
  "scanner": {
    "database_path": null,
    "template_cache_size": 16,
    "early_exit_threshold": 0.0,
    "confidence_gap": 0.0,
    "debug_mode": false,
    "extract_icons": false,
    "screenshots_folder": ""
  },
  "stockpile_types": {
    "encampment": [],
    "keep": [],
    "safe_house": [],
    "relic_base": [],
    "bunker_base": [],
    "border_base": [],
    "town_base": [],
    "underground_fortress": [],
    "bms_longhook": [],
    "storage_depot": [],
    "seaport": [],
    "aircraft_depot": []
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
  "notifications": {
    "enabled": false,
    "notifiers": []
  },
  "gui": {
    "config_level": "basic",
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
| **API Server** | | | |
| `FS_API_SERVER__CORS_ALLOW_ORIGINS` | JSON array | `[]` | CORS allowed origins (empty by default) |
| `FS_API_SERVER__HOST` | string | `"127.0.0.1"` | Server bind host |
| `FS_API_SERVER__PORT` | integer | `8000` | Server bind port |
| `FS_API_SERVER__WORKERS` | integer | `1` | Number of worker processes |
| `FS_API_SERVER__RELOAD` | boolean | `false` | Enable auto-reload |
| `FS_API_SERVER__LOG_LEVEL` | string | `"info"` | Server log level (`"debug"`, `"info"`, `"warning"`, `"error"`) |
| `FS_API_SERVER__ENABLE_MEMORY_MONITORING` | boolean | `false` | Enable memory monitoring and `/memory/*` endpoints |
| `FS_API_SERVER__AUTO_TRIM_MEMORY` | boolean | `true` | Auto-trim memory after scans to prevent fragmentation |
| `FS_API_SERVER__WEB_ICON_MOD` | string | `"vanilla"` | Mod for web interface icons |
| **API Authentication** | | | |
| `FS_API_AUTH__AUTH_TYPE` | string\|null | `null` | API auth type (`"basic"`, `"bearer"`, or `null`) |
| `FS_API_AUTH__AUTH_TOKEN` | string\|null | `null` | API authentication token |
| **Logging** | | | |
| `FS_LOGGING__LOGGERS` | JSON object | `{}` | Per-logger level overrides (see special syntax below) |
| `FS_LOGGING__LOGGERS__<LOGGER_NAME>` | string | N/A | Logger-specific level (e.g., `__foxhole_stockpiles`, `__uvicorn`) |
| `FS_LOGGING__LOG_LEVEL` | string | `"INFO"` | Global log level |
| `FS_LOGGING__LOG_FORMAT` | string | `"[%(asctime)s] %(levelname)s [%(name)s] %(message)s"` | Log format string |
| `FS_LOGGING__DATE_FORMAT` | string | `"%Y-%m-%d %H:%M:%S"` | Date format |
| `FS_LOGGING__ROTATE_LOGS` | boolean | `false` | Enable log rotation |
| `FS_LOGGING__LOG_FILE` | string\|null | `null` | Log file path |
| **Output** | | | |
| `FS_OUTPUT__HANDLERS` | JSON array | `[]` | List of output handler configurations (see examples below) |
| **Scanner** | | | |
| `FS_SCANNER__DATABASE_PATH` | string | `null` | Template database path |
| `FS_SCANNER__TEMPLATE_CACHE_SIZE` | integer | `16` | Max resolution databases to cache (0-16) |
| `FS_SCANNER__EARLY_EXIT_THRESHOLD` | float | `0.0` | Early exit threshold |
| `FS_SCANNER__CONFIDENCE_GAP` | float | `0.0` | Confidence gap for alternative candidates |
| `FS_SCANNER__DEBUG_MODE` | boolean | `false` | Enable debug image output |
| `FS_SCANNER__EXTRACT_ICONS` | boolean | `false` | Extract icons to folder for debugging |
| `FS_SCANNER__SCREENSHOTS_FOLDER` | string | `""` | Folder to save screenshots (empty to disable) |
| **External Tools** | | | |
| `FS_EXTERNAL_TOOLS__REPAK` | string\|null | `null` | Path to repak executable |
| `FS_EXTERNAL_TOOLS__UMODEL` | string\|null | `null` | Path to umodel executable |
| `FS_EXTERNAL_TOOLS__UASSETGUI` | string\|null | `null` | Path to UAssetGUI executable |
| **Database Builder** | | | |
| `FS_DATABASE_BUILDER__CATALOG_FILE` | string\|null | `null` | Path to catalog.json |
| `FS_DATABASE_BUILDER__TARGET_RESOLUTIONS` | JSON array\|null | `null` | Resolutions to generate |
| `FS_DATABASE_BUILDER__WORKERS` | integer\|null | `null` | Worker processes (null = auto) |
| **Notifications** | | | |
| `FS_NOTIFICATIONS__ENABLED` | boolean | `false` | Enable notifications |
| `FS_NOTIFICATIONS__NOTIFIERS` | JSON array | `[]` | List of notifier configs |
| **GUI** | | | |
| `FS_GUI__CONFIG_LEVEL` | string | `"basic"` | Config level (basic/advanced/developer) |
| `FS_GUI__MINIMIZE_TO_TRAY` | boolean | `false` | Minimize to tray on close |
| `FS_GUI__LANGUAGE` | string | `"en"` | GUI language code |
| **SAV Processing** | | | |
| `FS_SAV_PROCESSING__SAV_FILE_PATH` | string\|null | `null` | Path to the Foxhole `.sav` file to process |
| `FS_SAV_PROCESSING__POLL_INTERVAL` | float | `1.0` | Polling interval in seconds for monitoring mode (0.1–60.0) |
| `FS_SAV_PROCESSING__EMIT_ALL_ON_START` | boolean | `true` | Emit all stockpiles on first read |

**Note:** For JSON values (arrays/objects), use proper JSON syntax in the environment variable:
```bash
export FS_API_SERVER__CORS_ALLOW_ORIGINS='["https://example.com"]'
```

#### Per-Logger Level Configuration

The `loggers` setting has special syntax for environment variables. You can set logger-specific levels in two ways:

**Method 1: Individual logger variables (recommended)**
```bash
export FS_LOGGING__LOGGERS__foxhole_stockpiles=DEBUG
export FS_LOGGING__LOGGERS__uvicorn=WARNING
export FS_LOGGING__LOGGERS__httpx=ERROR
```

**Method 2: JSON object**
```bash
export FS_LOGGING__LOGGERS='{"foxhole_stockpiles":"DEBUG","uvicorn":"WARNING"}'
```

**In config file:**
```json
{
  "logging": {
    "loggers": {
      "foxhole_stockpiles": "DEBUG",
      "uvicorn": "WARNING",
      "httpx": "ERROR"
    }
  }
}
```

Valid log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

When a logger-specific level is set, it overrides the global `log_level` for that logger only.

#### Output Handlers Configuration

The `handlers` setting is a JSON array. Configure via environment variable:

**Single handler (return results to API caller):**
```bash
export FS_OUTPUT__HANDLERS='[{"name":"API Response","format":{"type":"json"},"handler":{"type":"return"}}]'
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
  {"name":"API Response","format":{"type":"json"},"handler":{"type":"return"}},
  {"name":"Backup","format":{"type":"json"},"handler":{"type":"file","path":"backup.json"}}
]'
```

Handler types: `return`, `file`, `webhook`, `console`
Format types: `json`, `csv`, `tsv`
