<!-- Generated: 2026-06-21 | Branch: main | Token estimate: ~950 -->

# Data Models, Config & Database

All models are Pydantic v2, strict validation (`extra="forbid"`),
JSON-serializable. Enums are `StrEnum`.

## Core output models

### Stockpile (`models/stockpile.py`)
```python
class Stockpile(BaseModel):
    name: str = ""
    type: StockpileType = UNDEFINED
    hex: str | None = None            # map region name (SAV)
    coords: StockpileCoords | None    # map coordinates (SAV)
    is_reserve: bool = False
    items: list[StockpileItem]
    timestamp: datetime               # serialized "%Y-%m-%dT%H:%M:%S"
    shard: str | None = None
    ingame_timestamp: str | None = None
    resolution: str | None = None
    errors: list[str] | None = None
    raw_timestamp: int | None = None  # ticks, excluded from serialization
    def to_key(self) -> str           # type:hex:coords:name — SAV change-tracking
```

### StockpileItem (`models/stockpile_item.py`)
```python
class StockpileItem(BaseModel):
    code: str
    quantity: int = -1                # int (ge=-1)
    crated: bool = False
    confidence: float | None          # 0..1, NCC match
    x: int | None = None              # icon pixel X (OCR source only)
    y: int | None = None              # icon pixel Y (OCR source only)
    candidates: list[ItemCandidate] | None  # within confidence_gap; excluded unless present
```
Custom `model_serializer` emits `candidates` only when non-empty.

### Other runtime models (`models/`)
- `scan_result.py` `ScanResult` — `{success, data, error, processing_time_ms}` (CLI/scan worker)
- `catalog_item.py` `CatalogItem` — item metadata (`cratable`, faction, category, icon)
- `match_result.py` `MatchResult` — `{code, ncc_score, phash_distance, resolution, mod, crated}`
- `item_candidate.py` `ItemCandidate` — alternative match (code, confidence)
- `icon_template.py` `IconTemplate` — template (image, code, faction, category, mod, crated, resolution, phash)
- `stockpile_coords.py` `StockpileCoords` — `{x, y}` normalized map coords (`to_key()`)
- `database_statistics.py`, `detected_icon_info.py`, `stockpile_image_regions.py`
- `memory_snapshot.py`, `request_memory_stats.py` — memory monitoring
- `mod_import_config.py`, `mod_import_progress.py`, `mod_import_result.py`, `pak_validation_result.py` — mod/asset import (uses `TemplateSettings`)
- `notification.py`

### External engine models (`fs_ocr` — Rust PyPI pkg, NOT in repo)
The external `fs-ocr` exposes `StockpileScanner`, `ScanConfig`,
`fs_ocr.Stockpile`, `fs_ocr.StockpileItem`. The runtime adapts them in
`services/scanner.py`; only `ScanConfig(confidence_gap=...)` is passed through.

## Enums (`enums/`)

| Enum | Values |
|---|---|
| `StockpileType` | ~28 in-game structures (Encampment, Keep, Safe House, Relic Base, Bunker T1/T2/T3, Border/Town T1/T2/T3, Underground Fortress, BMS Longhook/Bluefin, Storage Depot, Seaport, Aircraft Depot, Hospital, Refinery, Maintenance Tunnel, facility/factory types) + Undefined. Values are UE asset names |
| `ItemFaction` | Colonials, Wardens, Neutral |
| `ItemCategory` | 20+ (Ammo, AT Ammo, Weapons, … Vehicles) |
| `SupportedLanguage` | en, pt, fr, de, ru, zh, … |
| `SupportedResolution` | 16 (664px … 2880px) |
| `OutputFormat` | JSON, CSV, TSV |
| `OutputDestination` | return, file, webhook, console, **sheets** |
| `OutputHandlerType` | return, file, webhook, console, **google sheets** |
| `AuthType` | basic, bearer, forward — now only for the **webhook output handler** (forward = pass a client header through) |
| `EventType` | scan started/scanned/failed (+ unused legacy `SERVER_*`) |
| `ConfigLevel`, `NotifierType` | config scope, notifier kinds |

## Configuration (`core/settings/`)

### AppSettings root (schema **v11**)
```python
class AppSettings(BaseSettings):
    config_version: int        # CURRENT_VERSION = 11
    external_tools: ExternalToolsSettings
    logging: LoggingSettings
    output: OutputSettings
    scanner: ScannerSettings
    database_builder: DatabaseBuilderSettings
    notifications: NotificationsSettings
    gui: GUISettings
    sav_processing: SavProcessingSettings
```
(`api_server` + `api_auth` removed in v10; `stockpile_types` removed in v11.)
`sections/templates.py` (`TemplateSettings`) is consumed by mod-import models —
not a top-level field. (The old `OCRSettings` icon-geometry model was removed; its
one live value is `fs_tools/constants.py:ICON_BOX_SCALE = 64/2160` (fs_tools-only).)

### ScannerSettings (`sections/scanner.py`)
`database_path`, **`capture_key`** (global hotkey, e.g. `"F9"`; `None` disables
capture), `early_exit_threshold`, `confidence_gap`, `screenshots_folder`. The
runtime `Scanner` reads `database_path` + `confidence_gap` (passed to
`fs_ocr.ScanConfig`); the GUI binds the hotkey from `capture_key` and saves each
capture to `screenshots_folder` when set. `early_exit_threshold` is consumed by
the `fs_tools` candidate inspector, not the runtime.

### OutputSettings (`sections/output/`)
`OutputSettings.handlers: list[OutputHandlerConfig]`; per-handler models:
`console_handler.py`, `file_handler.py`, `webhook_handler.py` (`auth_type` +
`token`/`client_auth_header`), `return_handler.py`, **`sheets_handler.py`**
(`creds_path`, `spreadsheet_url`, `sheet_id`, `start_cell`, `row_format`), plus
format models `json_format.py`, `csv_format.py`. `handler_config.py` is the
discriminated-union wrapper.

### Sources & migration
Priority: env `FS_<SECTION>__<KEY>` → JSON file (platform config dir,
`json_settings_source.py`) → defaults. Stepwise upgrade in `config_migrator.py`
(v1 → … → 11). v9→v10 drops `api_server`/`api_auth`; v10→v11 drops `stockpile_types`.

## Template database (HDF5) — owned by `fs_tools`

`fs_tools/template_db/template_database.py` (read/write) +
`template_manager.py` (matching) + `icon_manager.py`. The external `fs-ocr`
engine reads this DB at scan time; the runtime no longer touches it directly.

```
database.h5
├── metadata        {version, format:"hdf5", created_at}
├── resolution_664px
│   ├── images      (N, H, W, 3) uint8
│   ├── codes / factions / categories / mods   (N,) string
│   ├── phashes     (N,) uint64
│   └── cratable    (N,) bool
└── ... 15 more resolution groups (664px … 2880px)
```

- All templates scaled relative to 1920px base; multi-mod (vanilla, airborne, community).
- Two-phase match: pHash prefilter → NCC scoring → pixel-diff tiebreaker (inside engine/tooling).

## Catalog JSON (`data/catalog.json`)

Item metadata: `code`, `name`, `category`, `faction`, `cratable`, icon ref.
`cratable` ← `ItemProfileData.bIsCratable` (items) or presence of
`MassProductionFactory` in `ProductionCategories` (vehicles). Read via
`services/catalog_service.py` (cached `get_catalog_service()`, `get_display_name`).

## SAV data

Parsed via `services/sav_parser.py` → `fs-sav` (Rust). `SaveFileProcessor`
produces `list[Stockpile]` with `hex`/`coords`/`is_reserve`/`raw_timestamp`
populated (no `x`/`y`); change-tracking keyed by `Stockpile.to_key()`.

## Key files
1. `models/stockpile.py`, `models/stockpile_item.py`
2. `core/settings/app_settings.py` + `config_migrator.py` (v11)
3. `core/settings/sections/scanner.py` — incl. `capture_key`
4. `core/settings/sections/output/` — handler + format models
5. `fs_tools/template_db/` — HDF5 access + matching
