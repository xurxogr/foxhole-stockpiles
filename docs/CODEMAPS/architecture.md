<!-- Generated: 2026-06-21 | Branch: main | Token estimate: ~950 -->

# Architecture & Design Patterns

**Type:** multi-package Python workspace (flat layout), **2 installable packages**.
Config schema **v9**.

## Package boundaries

```
foxhole_stockpiles ──depends──> fs-ocr (external Rust PyPI pkg)
        │                          ▲
        │                          │ adapter: services/scanner.py
        └── fs_tools (independent app: builds the HDF5 DB fs-ocr consumes)
```

- **foxhole_stockpiles** — user-facing runtime: CLI, REST API, web UI, GUI, SAV.
  Talks to the OCR engine only through `services/scanner.py`.
- **fs_tools** — build-time tooling (catalog, template DB, asset extraction).
  Self-contained: own `core/settings`, `models`, `gui`, `i18n`. Owns the HDF5
  template DB read/write code under `fs_tools/template_db/`.
- **fs-ocr** — external Rust OCR engine (PyPI `fs-ocr>=1.0.4`). NOT in this repo
  (the former in-repo `fs_ocr` package was deleted in commit `b0e8b6e`).

## Design philosophy

1. **Service layer** — focused single-responsibility classes, constructor injection.
2. **External OCR engine behind a thin seam** — `services/scanner.py` is the one
   module aware of `fs_ocr`; it adapts engine types to runtime models.
3. **Multi-handler output** — one result list fans out to console/file/webhook/response/sheets.
4. **Event-driven notifications** — decoupled via `EventBus` (`core/events/bus.py`).
5. **Config as code** — Pydantic settings, env overrides, versioned migration.

## OCR scan pipeline (screenshot → structured data)

Seam: `services/scanner.py` → `Scanner.scan()` / `build_scanner()`.

```
image (bytes | path | NDArray)
  │  _coerce_image()  → BGR uint8 ndarray (cv2)
  ▼
fs_ocr.StockpileScanner(database_path)          # external Rust engine
  .set_config(fs_ocr.ScanConfig(confidence_gap))
  .scan(img, faction)  → fs_ocr.Stockpile       # runs in asyncio.to_thread
  │   (detection, template match, Tesseract quantity OCR all inside Rust)
  ▼  _to_runtime_stockpile()  → json.loads(result.to_json())
     • map external StockpileType name → runtime StockpileType (tiers collapse)
     • map external items → runtime StockpileItem (code, quantity, crated,
       confidence, x, y)
  ▼ Stockpile model (foxhole_stockpiles.models)
  ▼ services/output_coordinator.py → handlers/* (first non-None result wins)
```

Faction filter: runtime `ItemFaction` → external string (`"wardens"`/`"colonials"`);
`NEUTRAL`/`None` → no filter.

## SAV pipeline (`.sav` world file → stockpile data)

```
War.sav (+ map data)
  ▼ services/savefile_processor.py (SaveFileProcessor)
  ▼ services/sav_parser.py ──delegates──> fs-sav (Rust lib)
  ▼ list[Stockpile] with hex/coords/is_reserve/raw_timestamp populated
  ▼ services/output_coordinator.py → handlers/*
```

SAV-sourced `Stockpile`s carry map metadata (`hex`, `coords`, `is_reserve`) and a
`raw_timestamp` (excluded from serialization) used for change-tracking via
`Stockpile.to_key()`. OCR-sourced items carry `x`/`y` pixel coords instead.

## Entry surfaces

| Surface | Module | Notes |
|---|---|---|
| CLI `fs` | `cli/app.py` (Typer) | `scan` `serve` `gui` `sav` |
| REST API | `api/server.py` (FastAPI) | see backend.md |
| Web UI | `api/web/routes.py` (Jinja) | upload form |
| Desktop GUI | `gui/app.py` (PySide6) | |
| Tooling | `fs_tools/cli.py`, `fs_tools/gui` | builders/extractors |

## Settings architecture

`core/settings/app_settings.py` → `AppSettings(BaseSettings)`, schema **v9**.
Top-level sections: `api_server`, `api_auth`, `external_tools`, `logging`,
`output`, `scanner`, `stockpile_types`, `database_builder`, `notifications`,
`gui`, `sav_processing`. (`OCRSettings` from `sections/ocr.py` is now a geometry
model used by GUI/tooling for icon-region math; `TemplateSettings` is consumed by
mod-import models — neither is a top-level field.)

Source priority (highest→lowest): env (`FS_<SECTION>__<KEY>`) → JSON file in
platform config dir → defaults. Stepwise migration via `ConfigMigrator`
(`CURRENT_VERSION = 9`).

## Event system

`core/events/bus.py` — `EventBus.emit(EventType, data)` / `subscribe(...)`.
Decouples NotificationService (Discord), logging, and memory metrics from the
pipeline. Events: server started/stopped, scan started/completed/failed, mod imported.

## Error handling

- Validate at boundaries (image decode, Pydantic config, DB existence).
- `Scanner.__init__` raises `ValueError` (no `database_path`) / `FileNotFoundError`.
- API maps to HTTP codes (401 auth, 429 rate/concurrency, 503 engine/DB).
- `ScanResult` envelope: `{success, data, error, processing_time_ms}`.

## Design decisions (rationale)

- **External Rust OCR engine:** the matching + OCR pipeline (formerly
  ~3k lines of Python in `fs_ocr/_impl/`) is now a compiled Rust dependency for
  speed; the runtime keeps only a thin adapter seam.
- **Template DB owned by fs_tools:** only the builder/tooling needs HDF5
  read/write at runtime the engine reads the DB itself.
- **HDF5 over pickle:** structured, queryable, language-agnostic, no exec risk.
- **EventBus:** multiple async subscribers without tight coupling.

> NOTE: CLAUDE.md describes a future "named pipelines" config
> (`AppSettings.pipelines`, `general.mode`, migrator v11). That is NOT on this
> branch — current config is flat sections at schema v9.

## Key files

1. `services/scanner.py` — OCR seam over external `fs_ocr`
2. `services/output_coordinator.py` — output routing (list-based)
3. `services/savefile_processor.py` + `sav_parser.py` — SAV pipeline
4. `core/settings/app_settings.py` — configuration (v9)
5. `fs_tools/template_db/template_manager.py` — icon matching / DB access
