<!-- Generated: 2026-06-21 | Branch: main | Source files: ~225 (.py) | Token estimate: ~900 -->

# Foxhole Stockpiles — Codemap Index

**Last Updated:** 2026-06-21
**Version:** 0.4.0 | **Config schema:** v9 | **Python:** 3.12+

## What it is

Computer-vision + OCR system that extracts structured item data from Foxhole
screenshots, and parses Foxhole `.sav` world files. Screenshot pipeline:
detect stockpile UI → match icons → read quantities → format output
(JSON/CSV/TSV/Sheets) → route to sinks. The OCR engine itself is now an
**external Rust package** (`fs-ocr` on PyPI); this repo is the runtime + tooling
around it.

## Two packages, two apps

```
┌──────────────────────────────────┬──────────────────────────────┐
│ foxhole_stockpiles               │ fs_tools                     │
│ (runtime app)                    │ (asset/db tooling)           │
├──────────────────────────────────┼──────────────────────────────┤
│ CLI `fs`, API server, web UI,    │ CLI `fs-tools`, tools GUI,   │
│ PySide6 GUI, SAV processing,     │ catalog/db/template builders,│
│ output routing, OCR seam         │ uasset extraction, template  │
│ (services/scanner.py)            │ DB read/write (template_db/) │
│ ~125 .py                         │ ~100 .py                     │
└──────────────────────────────────┴──────────────────────────────┘
```

The in-repo `fs_ocr` package was **removed** (commit `b0e8b6e`). OCR is now the
external `fs-ocr>=1.0.4` (Rust). The runtime's only contact point is
`foxhole_stockpiles/services/scanner.py`, which adapts the engine's
`fs_ocr.Stockpile` to the runtime `Stockpile` model. The HDF5 template DB code
moved to `fs_tools/template_db/`.

## Entry points (`pyproject.toml [project.scripts]`)

| Command | Target | Purpose |
|---|---|---|
| `fs` | `foxhole_stockpiles.cli.app:main` | Typer CLI — `scan`, `serve`, `gui`, `sav` |
| `fs-tools` | `fs_tools.cli:main` | Asset/database tooling CLI |
| `fs-gui` | `foxhole_stockpiles.gui.app:launch_gui` | PySide6 desktop app |
| `fs-tools-gui` | `fs_tools.gui:run_gui` | PySide6 tooling app |

(`fs-ocr` CLI entry point removed along with the in-repo engine.)

## foxhole_stockpiles modules

- **cli/** — Typer app (`app.py`); commands `scan`, `serve`, `gui`, `sav`; `_settings.py` loads `AppSettings`, `_console.py` Rich output.
- **api/** — FastAPI `server.py`, `auth.py` (Basic/Bearer; forward unsupported), `scan_limiter.py` (concurrency cap), `memory_middleware.py`, `dependencies.py` (DI), `web/` (Jinja HTML upload UI).
- **services/** — `scanner.py` (**OCR seam → external `fs_ocr`**), `output_coordinator.py` (sink routing), `catalog_service.py`, `notification_service.py`, `memory_monitor.py`, `sav_parser.py`, `savefile_processor.py`.
- **core/** — `settings/` (Pydantic `AppSettings` v9 + `config_migrator.py` + nested `sections/`), `events/bus.py` (EventBus), `logging.py`, `utils.py`, `version.py`.
- **models/** — Pydantic v2: `stockpile.py` (now with `hex`/`coords`/`is_reserve`/`to_key()`), `stockpile_item.py`, `catalog_item.py`, `match_result.py`, `scan_result.py`, SAV/mod-import models, memory-stat models.
- **handlers/** — output sinks: `console.py`, `file.py`, `webhook.py`, `response.py`, **`sheets.py`** (Google Sheets); interface in `base_handler.py`. Handlers now take `list[Stockpile]`.
- **notifiers/** — `discord.py` (+ `base.py`).
- **enums/** — StrEnums: stockpile_type (~28), item_faction, item_category, supported_language, supported_resolution, output_format/destination/handler_type, auth_type, event_type, config_level, notifier_type.
- **gui/** — PySide6 desktop app (widgets, config tabs, scan workers).
- **connectors/**, **constants/**, **i18n/** — webhook connector, stockpile-text tables, translations.

## See also

- `architecture.md` — package boundaries, scan & SAV data flow, patterns
- `backend.md` — API routes, middleware, CLI command flow, output routing
- `data.md` — config schema (v9), Pydantic models, HDF5 template DB
- `dependencies.md` — libraries, external tools, Rust sibling packages

## Five files to read first

1. `foxhole_stockpiles/services/scanner.py` — the OCR seam over external `fs_ocr`
2. `foxhole_stockpiles/cli/commands/scan.py` — wires scanner → output
3. `foxhole_stockpiles/api/server.py` — REST entry point
4. `foxhole_stockpiles/services/output_coordinator.py` — sink fan-out
5. `foxhole_stockpiles/core/settings/app_settings.py` — configuration root (v9)
