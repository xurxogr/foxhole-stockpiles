<!-- Generated: 2026-06-21 | Branch: main | Token estimate: ~850 -->

# CLI, GUI Capture & Local Pipeline

No REST server — this is a desktop app. "Backend" here means the CLI commands,
the GUI capture flow, the OCR seam, and output routing.

## CLI `fs` (Typer)

**Entry:** `cli/app.py:main`. Settings via `cli/_settings.py` (honours
`--config <path>`), Rich output via `cli/_console.py`. No subcommand → GUI.

| Command | Module | Flow |
|---|---|---|
| `fs scan` | `cli/commands/scan.py` | `ScannerSettings` → `services.scanner.build_scanner` (external `fs_ocr`) → `OutputCoordinator` → `ScanResult`/printed output |
| `fs gui` | `cli/commands/gui.py` | launches PySide6 desktop app |
| `fs sav` | `cli/commands/sav.py` | `SaveFileProcessor` (resolves `.sav` + map data) → `OutputCoordinator` |

Asset/DB tooling lives in the separate `fs-tools` CLI.

## Screenshot capture (GUI)

```
scanner.capture_key (e.g. "F9")
  ▼ gui/utils/hotkey_listener.py — pynput GlobalHotKeys, runs in its own thread
     to_global_hotkey("Ctrl+F3") → "<ctrl>+<f3>"   (Meta→cmd)
  ▼ emits a Qt signal → CapturePanel slot on the GUI thread
  ▼ gui/utils/capture_scan_worker.py  LocalScanWorker(QThread)
       services/capture.py  capture_window()  → PNG bytes
       services/local_scan.py  LocalScanService.scan(bytes) → Stockpile → outputs
```

`services/capture.py`:
```python
_WINDOW_TITLE_PREFIX = "War"   # hardcoded; the Foxhole window is titled "War"
def capture_window() -> bytes  # raises CaptureError on:
    #   - pywinctl/Pillow unavailable (headless)
    #   - no window titled "War*"
    #   - window minimized / not active
    # else: pywinctl client frame → PIL ImageGrab(all_screens=True) → PNG
```

## OCR seam (`services/scanner.py`)

```python
class Scanner:
    def __init__(self, settings: ScannerSettings):
        # raises ValueError / FileNotFoundError if database_path bad
        self._scanner = fs_ocr.StockpileScanner(database_path=...)
        self._scanner.set_config(fs_ocr.ScanConfig(confidence_gap=...))
    async def scan(self, image, faction=None) -> Stockpile      # asyncio.to_thread
    def scan_sync(self, image, faction=None) -> Stockpile

def build_scanner(settings: ScannerSettings) -> Scanner
```
Adapter `_to_runtime_stockpile()` parses `fs_ocr.Stockpile.to_json()` and maps
the external `StockpileType` name + items to runtime models.

## Local scan service (`services/local_scan.py`)

```python
class LocalScanService:
    def __init__(self, settings: AppSettings):
        self._scanner = build_scanner(settings.scanner)        # built once
        self._output_coordinator = OutputCoordinator(settings.output)
    def scan(self, image, faction=None) -> Stockpile:
        stockpile = self._scanner.scan_sync(image, faction=...)
        asyncio.run(self._output_coordinator.handle_output(stockpiles=[stockpile]))
        return stockpile
```
Backs both the capture worker and the GUI "scan a file" action. The `fs scan`
CLI wires the same scanner + `OutputCoordinator` directly.

## Output routing (`services/output_coordinator.py`)

```python
async def handle_output(stockpiles: list[Stockpile], **kwargs) -> dict | None:
    for cfg in output_settings.handlers:
        result = await self._create_handler(cfg).handle(stockpiles=..., **kwargs)
        if result is not None and out is None:
            out = result   # first non-None (e.g. ReturnHandler) wins
    # all handlers run even if one raises (errors logged, not propagated)
```

Handlers (`handlers/`), all `handle(stockpiles: list[Stockpile])`:
`console.py`, `file.py` (JSON/CSV/TSV), `webhook.py` (HTTP POST, supports
basic/bearer/**forward** auth), `response.py` (`ReturnOutputHandler` → returns
the dict), **`sheets.py`** (Google Sheets append). Interface: `base_handler.py`.

Webhook **forward auth**: `WebhookHandlerSettings.auth_type="forward"` +
`client_auth_header` — the per-call `token` kwarg is forwarded as that header.

## GUI capture panel (`gui/widgets/capture_panel.py`)

`CapturePanel` is the main window's central widget:
- **Start/Stop Capture** — toggles the `HotkeyListener`; warns if
  `scanner.capture_key` unset or the scanner can't be built (no DB).
- **Scan a file** (menu) — local scan of a chosen image.
- **SAV** column — one-shot scan + monitor (`gui/utils/sav_workers.py`).
- Live log table (`gui/utils/qt_log_handler.py`) + DB-config validation.

## Response / result models

- `ScanResult` (`models/scan_result.py`) — `{success, data: Stockpile|None, error, processing_time_ms}`; used by the CLI/scan worker.
- `Stockpile` / `StockpileItem` — see data.md.

## Scanner config (`core/settings/sections/scanner.py`)

`ScannerSettings`: `database_path`, **`capture_key`** (global hotkey),
`early_exit_threshold` (used by `fs-tools`), `confidence_gap`,
`screenshots_folder` (capture saving).

```bash
fs scan --image shot.png --config my.json
FS_SCANNER__DATABASE_PATH=/path/to/db.h5
FS_SCANNER__CAPTURE_KEY=F9
```

## Key files

1. `cli/commands/scan.py` — scan wiring
2. `services/capture.py` — window capture
3. `services/local_scan.py` — local scan → outputs
4. `services/scanner.py` — external OCR seam
5. `gui/widgets/capture_panel.py` — capture UI + hotkey
