<!-- Generated: 2026-06-21 | Branch: main | Token estimate: ~950 -->

# Architecture & Design Patterns

**Type:** multi-package Python workspace (flat layout), **2 installable packages**.
Config schema **v11**. Desktop app — **no REST server**.

## Package boundaries

```
foxhole_stockpiles ──depends──> fs-ocr (external Rust PyPI pkg)
        │                          ▲
        │                          │ adapter: services/scanner.py
        └── fs_tools (independent app: builds the HDF5 DB fs-ocr consumes)
```

- **foxhole_stockpiles** — desktop runtime: CLI, PySide6 GUI, screenshot
  capture, local scan, SAV processing, output routing. Talks to the OCR engine
  only through `services/scanner.py`.
- **fs_tools** — build-time tooling (catalog, template DB, asset extraction).
  Self-contained: own `core/settings`, `models`, `gui`, `i18n`. Owns the HDF5
  template DB read/write code under `fs_tools/template_db/`.
- **fs-ocr** — external Rust OCR engine (PyPI `fs-ocr>=1.0.4`). NOT in this repo
  (the former in-repo `fs_ocr` package was deleted in commit `b0e8b6e`).

## Design philosophy

1. **Service layer** — focused single-responsibility classes, constructor injection.
2. **External OCR engine behind a thin seam** — `services/scanner.py` is the one
   module aware of `fs_ocr`; it adapts engine types to runtime models.
3. **Capture-first, local-by-default** — a global hotkey captures the window and
   scans in-process; no network round-trip.
4. **Multi-handler output** — one result list fans out to console/file/webhook/response/sheets.
5. **Config as code** — Pydantic settings, env overrides, versioned migration.

## Capture + scan pipeline (hotkey → structured data)

```
global hotkey (pynput GlobalHotKeys)         scanner.capture_key, e.g. "F9"
  ▼  gui/utils/hotkey_listener.py → Qt signal → GUI thread
  ▼  gui/utils/capture_scan_worker.py (QThread)
services/capture.py  capture_window()        # pywinctl finds title "War*",
  │   must be active + non-minimized on any   #   PIL ImageGrab(all_screens) → PNG
  ▼  services/local_scan.py  LocalScanService.scan(image)
       │  services/scanner.py  Scanner.scan_sync(image, faction)
       │     fs_ocr.StockpileScanner(database_path)            # external Rust
       │       .set_config(fs_ocr.ScanConfig(confidence_gap))
       │       .scan(img, faction) → fs_ocr.Stockpile
       │     _to_runtime_stockpile() → runtime Stockpile
       ▼  services/output_coordinator.py → handlers/* (first non-None result wins)
```

The same `LocalScanService` backs the GUI "scan a file" menu action and the
`fs scan` CLI command. Faction filter: runtime `ItemFaction` → external string
(`"wardens"`/`"colonials"`); `NEUTRAL`/`None` → no filter.

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
| CLI `fs` | `cli/app.py` (Typer) | `scan` `gui` `sav`; no subcommand → GUI |
| Desktop GUI | `gui/app.py` → `gui/windows/main_window.py` | capture panel + SAV tools |
| Tooling | `fs_tools/cli.py`, `fs_tools/gui` | builders/extractors |

## Settings architecture

`core/settings/app_settings.py` → `AppSettings(BaseSettings)`, schema **v11**.
Top-level sections: `external_tools`, `logging`, `output`, `scanner`,
`database_builder`, `notifications`, `gui`, `sav_processing`.
(The capture hotkey is `scanner.capture_key`. `OCRSettings` from `sections/ocr.py`
is an icon-geometry model used by GUI/tooling; `TemplateSettings` is consumed by
mod-import models — neither is a top-level field.)

Source priority (highest→lowest): env (`FS_<SECTION>__<KEY>`) → JSON file in
platform config dir → defaults. Stepwise migration via `ConfigMigrator`
(`CURRENT_VERSION = 11`; v9→v10 drops `api_server`/`api_auth`, v10→v11 drops `stockpile_types`).

## GUI structure

`gui/windows/main_window.py` hosts `widgets/capture_panel.py` (central widget):
Start/Stop capture toggle (binds the hotkey listener), "scan a file" action, SAV
scan/monitor tools, and a live log table. Config dialog
(`windows/config_window.py`) has tabs: Scanner (incl. capture hotkey), Output,
Logging, GUI (+ Stockpile Types / Notifications / SAV at advanced level).

## Event system

`core/events/bus.py` — `EventBus.emit(EventType, data)` / `subscribe(...)`.
Decouples NotificationService (Discord) and metrics from the pipeline. Active
events: scan started/scanned/failed. (`SERVER_*` enum members remain but are
unused after the server removal.)

## Error handling

- Validate at boundaries (image decode, Pydantic config, DB existence).
- `Scanner.__init__` raises `ValueError` (no `database_path`) / `FileNotFoundError`.
- `services/capture.py` raises `CaptureError` (no window / minimized / inactive /
  unavailable platform); the GUI surfaces it in the log + a message box.

## Design decisions (rationale)

- **External Rust OCR engine:** the matching + OCR pipeline (formerly
  ~3k lines of Python) is now a compiled Rust dependency for speed; the runtime
  keeps only a thin adapter seam.
- **Server removed:** scanning is local from a captured screenshot, so the
  FastAPI/uvicorn stack and its config were dropped (schema v9→v10).
- **Template DB owned by fs_tools:** only the builder/tooling needs HDF5
  read/write; the engine reads the DB itself at scan time.
- **HDF5 over pickle:** structured, queryable, language-agnostic, no exec risk.

> NOTE: CLAUDE.md still describes the 3-package / FastAPI layout and a future
> "named pipelines" config — both stale on this branch (2 packages, no server,
> flat sections at schema v11).

## Key files

1. `services/scanner.py` — OCR seam over external `fs_ocr`
2. `services/capture.py` + `services/local_scan.py` — capture + local scan→output
3. `gui/widgets/capture_panel.py` — capture UI + hotkey
4. `services/output_coordinator.py` — output routing (list-based)
5. `core/settings/app_settings.py` — configuration (v11)
