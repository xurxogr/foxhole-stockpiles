<!-- Generated: 2026-06-21 | Branch: main | Token estimate: ~900 -->

# Backend, API & CLI

## CLI `fs` (Typer)

**Entry:** `cli/app.py:main`. Settings loaded via `cli/_settings.py`
(honours `--config <path>`), Rich output via `cli/_console.py`.

| Command | Module | Flow |
|---|---|---|
| `fs scan` | `cli/commands/scan.py` | `ScannerSettings` → `services.scanner.build_scanner` (external `fs_ocr`) → `OutputCoordinator` |
| `fs serve` | `cli/commands/serve.py` | launches uvicorn on `api.server:app` |
| `fs gui` | `cli/commands/gui.py` | launches PySide6 desktop app |
| `fs sav` | `cli/commands/sav.py` | `SaveFileProcessor` (resolves `.sav` + map data) → `OutputCoordinator` |

> Asset/DB tooling commands (build-db, gen-templates, catalog, add-mod/icon,
> inspect, extract-assets) live in the separate `fs-tools` CLI. The `fs-ocr`
> engine CLI was removed (engine is now an external Rust package).

## FastAPI server (`api/server.py`)

```python
app = FastAPI(title="Foxhole Stockpile Scanner API", version="0.4.0")
```

**Lifespan:** startup loads config + verifies DB; shutdown emits notifications +
clears DI caches.

### Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | no | health/version (`HealthResponse`) |
| POST | `/ocr/scan_image` | yes | main OCR; concurrency-limited; `multipart` image + `faction`/`language` query → `ScanResult` |
| GET | `/memory/stats` | yes | memory snapshot stats |
| POST | `/memory/gc` | yes | force GC |
| GET | `/memory/current` | yes | current memory |
| GET | `/memory/gc-stats` | yes | GC stats |
| GET | `/scan/stats` | yes | scan-limiter counters (queue wait, concurrency) |

**Web UI** (`api/web/routes.py`, `APIRouter`, auth-gated via `include_router(dependencies=[auth])`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Jinja upload form (`templates/`) |
| POST | `/web/scan` | form submit → HTML results |

(The former `/web/icon/{code}` route was dropped — runtime no longer serves
icons from the template DB.)

### scan_image handler shape

```python
@app.post("/ocr/scan_image", dependencies=[Depends(auth_dependency)])
async def scan_stockpile(
    request: Request,
    image: UploadFile,
    scanner: Annotated[Scanner, Depends(get_scanner)],
    output_coordinator: Annotated[OutputCoordinator, Depends(get_output_coordinator)],
    scan_limiter: Annotated[ScanLimiter, Depends(get_scan_limiter)],
    faction: ItemFaction | None = Query(None),
    language: SupportedLanguage | None = Query(None),
) -> Any
```

## Auth (`api/auth.py`)

`create_auth_dependency` builds a dependency from `APIAuthSettings`
(`auth_type` + single `auth_token`); `verify_auth` compares the `Authorization`
header with `secrets.compare_digest`:
- `auth_type` unset → no auth required
- `BEARER` → header must equal `Bearer <auth_token>`
- `BASIC` → header must equal `Basic <auth_token>` (`auth_token` = base64 `user:pass`)
- `FORWARD` → not supported for API auth (rejected by settings validator)

`auth_type` and `auth_token` must both be set or both unset (model validator).
Env: `FS_API_AUTH__AUTH_TYPE=bearer`, `FS_API_AUTH__AUTH_TOKEN=...`.

## Dependency injection (`api/dependencies.py`)

`@lru_cache` singletons: `get_scanner` (**wraps external `fs_ocr` engine**),
`get_output_coordinator`, `get_catalog_service`, `get_notification_service`,
`get_scan_limiter`. `clear_dependency_caches()` resets them on shutdown
(shuts down NotificationService first to unsubscribe event handlers).

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

## Middleware (`api/`)

1. **CORS** — origins from `api_server.cors_allow_origins`.
2. **Security headers** — CSP, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy` on HTML.
3. **MemoryMonitorMiddleware** (`memory_middleware.py`) — optional per-request memory tracking + auto-trim, gated by `api_server.enable_memory_monitoring`.

## Concurrency limiting (`api/scan_limiter.py`)

`ScanLimiter` wraps an `asyncio.Semaphore(max_concurrent_scans)` — caps
concurrent OCR scans **per worker** (effective = workers × max_concurrent_scans).
Tracks queue-wait stats (`ScanLimiterStats`). Exceeding capacity queues; not a
per-IP rate limiter.

## Output routing (`services/output_coordinator.py`)

```python
async def handle_output(stockpiles: list[Stockpile], **kwargs) -> dict | None:
    for cfg in output_settings.handlers:
        result = await self._create_handler(cfg).handle(stockpiles=..., **kwargs)
        if result is not None and out is None:
            out = result   # first non-None (e.g. ReturnHandler for API) wins
    # all handlers run even if one raises (errors logged, not propagated)
```

Handlers (`handlers/`): `console.py`, `file.py` (JSON/CSV/TSV), `webhook.py`
(HTTP POST), `response.py` (API return), **`sheets.py`** (Google Sheets append).
Interface: `base_handler.py` (`handle(stockpiles: list[Stockpile])`).

## Response models

- `ScanResult` — `{success, data: Stockpile|None, error, processing_time_ms}`.
- `Stockpile` / `StockpileItem` — see data.md.

## API server config (`core/settings/sections/api.py`)

`APIServerSettings`: `host`, `port`, `workers`, `reload`, `log_level`,
`max_concurrent_scans`, `enable_memory_monitoring`, `auto_trim_memory`,
`memory_trim_threshold`, `cors_allow_origins`, `max_upload_size_bytes`.

```bash
fs serve                          # via CLI
FS_API_SERVER__PORT=8000          # env override
FS_API_AUTH__AUTH_TYPE=bearer
FS_API_AUTH__AUTH_TOKEN=secret
```

## Key files

1. `cli/commands/scan.py` — scan wiring
2. `api/server.py` — routes + middleware
3. `api/dependencies.py` — DI singletons (`get_scanner`)
4. `services/scanner.py` — external OCR seam
5. `services/output_coordinator.py` — sink fan-out
