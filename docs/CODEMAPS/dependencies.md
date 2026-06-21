<!-- Generated: 2026-06-21 | Branch: main | Token estimate: ~800 -->

# Dependencies & External Tools

Source of truth: `pyproject.toml`. Python **3.12+**.

## Runtime dependencies

| Package | Min | Role |
|---|---|---|
| opencv-python-headless | 4.13.0.90 | image decode/coerce in the OCR seam |
| numpy | 2.4.5 | arrays / image buffers |
| pillow | 12.2.0 | image I/O |
| pytesseract | 0.3.13 | Tesseract wrapper (tooling / legacy paths) |
| h5py | 3.16.0 | HDF5 template DB (built/read by `fs_tools`) |
| pydantic | 2.13.4 | models / validation |
| pydantic-settings | 2.14.1 | env + file config |
| fastapi | 0.136.1 | REST API |
| uvicorn[standard] | 0.47.0 | ASGI server |
| python-multipart | 0.0.29 | upload form parsing |
| jinja2 | 3.1.0 | web UI templates |
| slowapi | 0.1.9 | (present) HTTP utilities |
| typer | 0.12.0 | CLI framework (`fs`, `fs-tools`) |
| **fs-ocr** | **1.0.4** | **external Rust OCR engine (replaces in-repo `fs_ocr`)** |
| **fs-sav** | 0.2.0 | Rust `.sav` parser |
| **google-api-python-client** | 2.196.0 | **Google Sheets output handler** |
| **google-auth-httplib2** | 0.4.0 | Google auth transport |
| **google-auth-oauthlib** | 1.4.0 | Google OAuth installed-app flow |
| PySide6 | 6.6 | desktop GUI (LGPL) |
| httpx | 0.28.1 | async HTTP (webhooks) |
| discord-webhook | 1.3.1 | Discord notifications |
| psutil | 7.2.2 | process/memory utils |
| memory-profiler | 0.61.0 | memory profiling |

## Sibling / external Rust packages

- **fs-ocr** (PyPI `fs-ocr>=1.0.4`) — the OCR engine. `StockpileScanner`,
  `ScanConfig`, `Stockpile`, `StockpileItem`. Backs `services/scanner.py`. The
  former in-repo `fs_ocr` Python package was deleted (commit `b0e8b6e`).
- **fs-sav** (PyPI) — backs `services/sav_parser.py`.

## External binaries

| Tool | Required for | Platform | Integration |
|---|---|---|---|
| **Tesseract OCR** (5.x) | OCR (consumed inside `fs-ocr`; tooling via `pytesseract`) | any | custom model `tessdata/renner_numbers.traineddata` |
| **repak** | PAK extraction (`fs-tools`) | Win/Linux | `connectors/` + `fs_tools` |
| **umodel(.exe)** | UE asset conversion (`fs-tools`) | Windows | `connectors/` + `fs_tools` |

`ExternalToolsSettings`: `repak_path`, `umodel_path`
(env `FS_EXTERNAL_TOOLS__REPAK_PATH`, …). Extractor/converter detected as
Windows or Linux independently; Linux extractor + Windows converter is valid.

## Google Sheets integration

`handlers/sheets.py` (`SheetsOutputHandler`) appends rows to a spreadsheet via
the Sheets v4 API. OAuth installed-app flow; token cached at `~/.fs_token`.
Config in `sections/output/sheets_handler.py` (`creds_path`, `spreadsheet_url`,
`sheet_id`, `start_cell`, `row_format`). `row_format` is a comma-list DSL
(`timestamp`, `structure_type`, `region`, `structure_x/y`, `stockpile_name`,
`item_code_name`, `item_display_name`, `item_quantity`, `item_crated`, …).

## Dev dependencies (`[project.optional-dependencies] dev`)

pytest 9.0.3 (+ asyncio 1.2, cov 7.1, xdist 3.8, qt 4.5), mypy 2.1 (strict),
ruff 0.15.13, pre-commit 4.6, type stubs (types-requests, types-psutil, h5py-stubs).

**Quality gates:** `ruff check` / `ruff format`; `mypy` (strict, pydantic plugin);
`pytest` (≥80% coverage target, `--cov=foxhole_stockpiles --cov=fs_tools`).
Ruff lint: `E,W,F,I,B,UP,D`, line length 100, preview rules on.

## Entry points (`pyproject.toml`)

```
[project.scripts]
fs        = foxhole_stockpiles.cli.app:main      # scan/serve/gui/sav
fs-tools  = fs_tools.cli:main
[project.gui-scripts]
fs-gui       = foxhole_stockpiles.gui.app:launch_gui
fs-tools-gui = fs_tools.gui:run_gui
```

(`fs-ocr` script removed; engine is an external dependency.)

Packaging: `tool.setuptools.packages.find` includes `foxhole_stockpiles*` +
`fs_tools*` (excludes `fs_tools.tests*`).

## Standalone dev scripts (`tools/`)

Not packaged — run directly:
- `crate_overlay_calibrator.py` — crate-overlay calibration tool
- `sync_stockpile_translations.py` — translation catalog sync
- `update_dependencies.py` — dependency bump helper

## Platforms

Linux / Windows / macOS / WSL2. On WSL2, `/mnt/c/...` ↔ `C:\...` path
conversion for Windows-compiled tools; temp dirs use Windows-accessible paths
when a Windows tool is in the chain.

## Config examples

```jsonc
// platform config dir
{ "config_version": 9,
  "scanner": { "database_path": "...templates.h5", "confidence_gap": 0.0 },
  "api_server": { "host": "0.0.0.0", "port": 8000, "max_concurrent_scans": 2 },
  "output": { "handlers": [ /* console/file/webhook/return/sheets */ ] },
  "sav_processing": { /* save dir / map data resolution */ } }
```
```bash
FS_SCANNER__DATABASE_PATH=/path/to/db.h5
FS_API_AUTH__AUTH_TYPE=bearer
FS_API_AUTH__AUTH_TOKEN=secret
```

## Licensing

Project MIT. Deps MIT/BSD/Apache; pytesseract GPLv3 (compatible);
PySide6 LGPLv3.

## Key files
1. `pyproject.toml` — declarations + entry points
2. `services/scanner.py` — external `fs-ocr` binding
3. `services/sav_parser.py` — `fs-sav` binding
4. `handlers/sheets.py` — Google Sheets integration
5. `core/settings/sections/external_tools.py` — tool paths
