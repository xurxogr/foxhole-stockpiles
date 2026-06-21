<!-- Generated: 2026-06-21 | Branch: main | Source files: ~220 (.py) | Token estimate: ~900 -->

# Foxhole Stockpiles — Codemap Index

**Last Updated:** 2026-06-21
**Version:** 0.4.0 | **Config schema:** v10 | **Python:** 3.12+

## What it is

Desktop app that extracts structured item data from Foxhole stockpile
screenshots, and parses Foxhole `.sav` world files. It is **capture-first**: a
global hotkey grabs the live Foxhole window, the OCR runs **in-process**, and the
result is routed to configured outputs (JSON/CSV/TSV/Sheets/webhook/console).
The OCR engine itself is an **external Rust package** (`fs-ocr` on PyPI); this
repo is the desktop runtime + tooling around it. There is no REST server.

## Two packages, two apps

```
┌──────────────────────────────────┬──────────────────────────────┐
│ foxhole_stockpiles               │ fs_tools                     │
│ (desktop runtime)                │ (asset/db tooling)           │
├──────────────────────────────────┼──────────────────────────────┤
│ CLI `fs`, PySide6 GUI (capture + │ CLI `fs-tools`, tools GUI,   │
│ SAV), screenshot capture, local  │ catalog/db/template builders,│
│ scan, output routing, OCR seam   │ uasset extraction, template  │
│ (services/scanner.py)            │ DB read/write (template_db/) │
│ ~120 .py                         │ ~100 .py                     │
└──────────────────────────────────┴──────────────────────────────┘
```

The in-repo `fs_ocr` package was **removed** (commit `b0e8b6e`). OCR is now the
external `fs-ocr>=1.0.4` (Rust). The runtime's only contact point is
`services/scanner.py`, which adapts the engine's `fs_ocr.Stockpile` to the
runtime `Stockpile` model. The FastAPI server was **removed** in favor of local
capture-and-scan. The HDF5 template DB code lives in `fs_tools/template_db/`.

## Entry points (`pyproject.toml [project.scripts]`)

| Command | Target | Purpose |
|---|---|---|
| `fs` | `foxhole_stockpiles.cli.app:main` | Typer CLI — `scan`, `gui`, `sav` (no subcommand → GUI) |
| `fs-tools` | `fs_tools.cli:main` | Asset/database tooling CLI |
| `fs-gui` | `foxhole_stockpiles.gui.app:launch_gui` | PySide6 desktop app |
| `fs-tools-gui` | `fs_tools.gui:run_gui` | PySide6 tooling app |

(The `serve` command and the in-repo `fs-ocr` CLI were both removed.)

## foxhole_stockpiles modules

- **cli/** — Typer app (`app.py`); commands `scan`, `gui`, `sav`; `_settings.py` loads `AppSettings`, `_console.py` Rich output.
- **services/** — `scanner.py` (**OCR seam → external `fs_ocr`**), `capture.py` (grab the Foxhole window), `local_scan.py` (`LocalScanService`: scan → outputs), `output_coordinator.py` (sink routing), `catalog_service.py`, `notification_service.py`, `memory_monitor.py`, `sav_parser.py`, `savefile_processor.py`.
- **core/** — `settings/` (Pydantic `AppSettings` v10 + `config_migrator.py` + nested `sections/`), `events/bus.py` (EventBus), `logging.py`, `utils.py`, `version.py`.
- **models/** — Pydantic v2: `stockpile.py` (`hex`/`coords`/`is_reserve`/`to_key()`), `stockpile_item.py` (`x`/`y`/`candidates`), `catalog_item.py`, `match_result.py`, `scan_result.py`, SAV/mod-import models, memory-stat models.
- **handlers/** — output sinks taking `list[Stockpile]`: `console.py`, `file.py`, `webhook.py`, `response.py` (return), **`sheets.py`** (Google Sheets); interface in `base_handler.py`.
- **notifiers/** — `discord.py` (+ `base.py`).
- **enums/** — StrEnums: stockpile_type (~28), item_faction, item_category, supported_language, supported_resolution, output_format/destination/handler_type, auth_type, event_type, config_level, notifier_type.
- **gui/** — PySide6 desktop app: `windows/` (main, config), `widgets/capture_panel.py` + `config_tabs/`, `utils/` (hotkey listener, capture+scan worker, SAV workers, log handler).
- **connectors/**, **constants/**, **i18n/** — webhook connector, stockpile-text tables, translations.

## See also

- `architecture.md` — package boundaries, capture & SAV data flow, patterns
- `backend.md` — CLI commands, GUI capture flow, output routing
- `data.md` — config schema (v10), Pydantic models, HDF5 template DB
- `dependencies.md` — libraries, external tools, Rust sibling packages

## Five files to read first

1. `services/scanner.py` — the OCR seam over external `fs_ocr`
2. `services/capture.py` + `services/local_scan.py` — capture + local scan→output
3. `gui/widgets/capture_panel.py` — hotkey capture panel (the main UI)
4. `services/output_coordinator.py` — output sink fan-out
5. `core/settings/app_settings.py` — configuration root (v10)
