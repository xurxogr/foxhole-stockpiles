# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-24

### Added
- **Local screenshot capture**: a configurable global hotkey (`scanner.capture_key`,
  e.g. `F9`) captures the active Foxhole window (title "War", any monitor) and
  scans it in-process, routing the result to the configured output handlers.
  New dependencies: `pywinctl`, `pynput` (with Pillow `ImageGrab`).
- **Google Sheets output handler** (`sheets`).
- **Clipboard stockpile scanning**: parses a stockpile list copied from the
  in-game UI (the localized export text) into structured stockpiles and routes
  them to the configured outputs, available from the GUI and the `fs clip`
  command. Item codes are resolved from the catalog and the stockpile faction is
  inferred from the items. Implemented in pure Python (no Rust dependency).
- **Faction on `Stockpile` output** (`faction`): populated only when the source
  provides it — read from `fs-sav` and `fs-ocr`, and inferred by item majority
  vote for clipboard scans. Omitted from output when unknown.

### Changed
- **OCR engine is now the external Rust package `fs-ocr`** (PyPI); the in-repo
  `fs_ocr` package was removed. The runtime talks to it through
  `services/scanner.py`. HDF5 template DB code moved to `fs_tools/template_db/`.
- Config schema migrated to **v13**; the capture hotkey lives at
  `scanner.capture_key`.
- **`Stockpile.type` is now a free-form string** instead of a fixed enum. Each
  source's value is normalized to a canonical name when recognized and otherwise
  passed through verbatim, so stockpile types added in new game updates are
  preserved instead of collapsing to `Undefined`. The `StockpileType` enum is
  retained only as the normalization target.
- **SAV processing sends every stockpile to the output handlers in a single
  call** (previously one call per map location). With a static file path this
  fixes the output being overwritten down to a single stockpile; each handler now
  decides its own per-location grouping.
- **Upgraded `fs-sav` to 0.3.0**, which fixes stockpile-type detection and adds
  the controlling faction to its output.
- **Merged the configurable input sections into a single GUI tab.**

### Fixed
- **Clipboard parsing uses the stockpile hex code** instead of the localized
  display name, so the `hex` field is stable across languages.
- **Faction parsing from `.sav` files** now recognizes the singular `Colonial`/
  `Warden` values emitted by `fs-sav` 0.3.0 (previously every stockpile came back
  as neutral).

### Removed
- **The GUI configuration levels** (basic/advanced/developer) and the
  `gui.config_level` setting (dropped in the v12→v13 migration): the levels only
  guarded the OCR/template internals that moved to `fs-ocr`/`fs-tools`, so they
  no longer gated anything. All settings tabs are now always visible.
- **The `notifications` config section, its GUI tab, and the Discord notifier**
  (dropped in the v11→v12 migration): the notifier stack was never wired into the
  scan flow, so configured notifications were never sent. Send scans to Discord
  via a webhook output handler instead.
- **Dead `fs scan` flags** `--language` and `--output-format`: both were accepted
  but had no effect (the engine auto-detects languages; output format is set per
  handler). The hidden legacy command aliases (`scanner`, `process-sav`,
  `ui`/`app`) were also removed.
- **The `stockpile_types` config section and its GUI tab** (dropped in the
  v10→v11 migration): the alias list was no longer consumed — stockpile-type
  detection happens inside the external `fs-ocr` engine.
- **Dead scanner settings** `template_cache_size`, `debug_mode`, and
  `extract_icons` (also dropped in v10→v11), plus the corresponding `fs scan`
  flags. (`early_exit_threshold` is kept for `fs-tools`' candidate inspector;
  `screenshots_folder` is kept and now saves each captured screenshot.)
- **The FastAPI REST server and everything around it**: the `api/` package, the
  `fs serve` command, all REST endpoints (`/ocr/scan_image`, `/health`,
  `/memory/*`, `/scan/stats`), the Jinja web UI, Docker deployment, the
  `api_server`/`api_auth` config sections (dropped in the v9→v10 migration), all
  `FS_API_*` env vars, and the `fastapi`/`uvicorn`/`slowapi`/`python-multipart`/
  `jinja2` dependencies. Scanning is now local.

## [0.4.0] - 2026-01-27

### Added
- **GUI Application**: Full-featured graphical interface with multiple panels
  - Server panel for start/stop control with status monitoring
  - Configuration dialog with tiered settings (Basic/Advanced/Developer)
  - Database builder for importing PAK files with validation and progress tracking
  - Catalog builder option under File menu
  - Database information menu showing mods and templates per resolution
  - Minimize to system tray on close
- **Internationalization (i18n)**: Translation support for the GUI (does not cover logging or CLI)
- **Web Frontend**: Minimalistic web interface to scan stockpiles and view results as a table
  - Save results as JSON and TSV formats
- **Catalog Builder Command**: `fs catalog` command to build catalog from PAK files
- **Mod Import Command**: `fs mod` command to automate importing mod PAK files into a database
- **Multiple Output Handlers**: Configure multiple output handlers, each with its own type
  - CSV and TSV format output support
  - Placeholders in file path for file output handlers
  - First handler that returns data provides the response
- **Stockpile Types**: Added Aircraft Depot and Underground Fortress to valid stockpile types
- **Database Visualizer**: Moved from tools/ to GUI application

### Changed
- GUI and server libs are now part of the default library installation
- Notifier usernames now display as "FS (xxx)" instead of just "xxx"
- Database path is now configurable in the database builder
- Workers option added to database builder (0 = autodetect)

### Fixed
- **Template Builder**: Don't create crate versions for items that can't be crated
- **GUI**: Fixed crash when closing window immediately after opening (Qt signals cleanup)
- **Path Fixes**: Fixed paths for tools when one is WSL and the other is Windows
- **Notification Fixes**:
  - Server stop notification now sent on GUI close by waiting for server thread
  - Notifications sent in correct order
  - Fixed duplicate notification handlers on server stop/start
  - Fixed sending stop server notifications

### Development
- Force wheel version to be >=0.46.2 due to vulnerabilities
- Updated libraries to latest versions
- Improved test coverage
- Mock Discord webhook in tests to prevent sending real messages
- Removed GUI from CI testing (tested locally only)
- Updated dependabot configuration

## [0.3.1] - 2025-12-24

### Fixed
- Windows executable not executing when run from command line (added missing entry point guard to fs.py)

## [0.3.0] - 2025-12-24

### Added
- **HDF5 Database Format**: Migrated from pickle to HDF5 for 20-40% memory reduction and faster loading
- **Memory Monitoring System**: Complete profiling with `/memory/stats` and `/memory/gc` API endpoints, automatic trimming after each scan
- **Git Version Tracking**: Startup logs show commit hash, date, and dirty status (baked into Docker images at build time)
- **Match Quality Statistics**: Scan logs include unique vs alternative matches to assess detection confidence
- **Notification System**: Discord webhooks for scan events with customizable message templates
- **Python 3.13 Support**: Docker images support both Python 3.12 and 3.13
- **jemalloc Integration**: Reduces memory fragmentation by 20-40 MB
- **Configurable Template Cache**: Control resolution database caching (0-16, default: 16 = all)
- **Multi-language OCR**: API and CLI support for specifying language (English, Portuguese, French, German, Russian, Chinese)
- **Confidence Gap Setting**: Configure threshold for returning alternative match candidates
- **Performance Documentation**: Detailed metrics in README (99.99% detection rate, 1-2s scan time)

### Changed
- **BREAKING**: Database format from .pkl to .h5 - existing databases must be regenerated with `fs generate-templates`
- **BREAKING**: Language, faction, and mod are now method parameters instead of global scanner settings
- **Configuration**: Split into logical sections (api, scanner, notifications, output) with separate format/destination settings
- **Architecture**: OCRCoordinator and OutputCoordinator are now stateless singletons for better memory efficiency
- **Early Exit Threshold**: Now defaults to 0.0 (disabled) for maximum accuracy instead of early termination
- **Memory Management**: Webhooks use persistent connections, automatic gc.collect() + malloc_trim() after scans

### Performance
- **Memory**: ~200 MB baseline, ~400 MB peak (27.5% faster scans, 20-40% less memory)
- **Detection**: 99.99% rate (4 undetected / 27,538 items in production)
- **Confidence**: 97.89% average (based on 1,000+ production scans)
- **Speed**: 1-2s per scan on consumer hardware (6+ cores)

### Documentation
- Added performance metrics and system requirements to README
- Added fs_config examples for different deployment scenarios
- Updated Docker documentation with Python 3.13 and jemalloc info
- Added Windows executable build to CI workflow

## [0.2.0] - 2025-10-19

### Added
- **New Command**: `fs add-icon` command for manual icon database management
- Added `extract_icons` option in scanner settings to save extracted icons from screenshots for debugging
- Added `--top` option to inspector command to show confidence of top N items in database (default: 5)
- Added average confidence to scan summary log messages
- Added low-confidence match reporting to error messages
- Added adaptive grey threshold detection based on darkest quantity box grey values
- Added option to save screenshots to a folder before processing (`screenshots_folder` setting)
- Added `exclude_codes` parameter to `get_candidates` method for better icon redetection
- Improved test coverage significantly across multiple modules

### Changed
- Replaced OpenCV with PIL for image loading and resizing in template generation
- Scanner now redetects icons when there is a conflict to improve accuracy
- Corrected image format handling to consistently use BGR format
- Made name detection coordinates larger to avoid cutting names in edge cases
- Adjusted name box detection coordinates to reduce empty gap to left of name
- Moved webhook response logging to debug level
- Reduced scanner verbosity - most logs moved to debug, leaving scan summary at info level
- Item confidence now displays with 3 decimal places for better precision

### Fixed
- Fixed stockpile type and name location detection with empty stockpiles
- Fixed subprocess handling in uasset_extractor to prevent resource leaks
- Fixed individual logger level configuration from settings not being applied
- Removed default value for early exit parameter in CLI to prevent overwriting configured value in `~/.fs_config`
- Fixed uasset tests after template refactoring
- Fixed test image handling by adding via Git LFS for complete CI test coverage
- Standardized CI to Python 3.12 for consistent coverage reporting
- Used `Resampling.LANCZOS` instead of deprecated `Image.LANCZOS` to fix mypy warnings

### Development
- Updated dependencies to latest versions
- Upgraded development tools from PyQt5 to PyQt6
- Added crate overlay calibrator tool for visualizing crate icon positioning
- Updated Codevoc configuration and improved test reporting
- Updated CLI documentation to match current usage

## [0.1.1] - 2025-10-05

### Fixed
- **Critical**: Fixed contour sorting and column tracking for accurate quantity detection in stockpile screenshots
- **Critical**: Fixed UTF-8 encoding when reading JSON config files on Windows (supports Russian/Chinese characters)
- Fixed webhook authentication header forwarding (requires `"webhook_auth_type": "forward"`)
- Fixed reading settings from `.fs_config` file
- Fixed test suite after authentication changes

### Changed
- Changed OCR to use per-call `--tessdata-dir` parameter instead of global `TESSDATA_PREFIX` environment variable
- Renamed custom OCR model from "custom" to "renner_numbers" for clarity
- Custom model now used only for quantity detection; standard Tesseract models used for text

### Added
- Added fuzzy matching for common OCR errors in stockpile type detection ("Seapon" → "Seaport")
- Added case-insensitive matching for stockpile type classification

### Documentation
- Updated configuration documentation with all available options
- Clarified that `renner_numbers` model is bundled and required for quantity detection
- Added platform-specific instructions for installing optional language packs (Russian, Chinese, Portuguese, French, German)
- Documented multilingual OCR support

## [0.1.0] - 2025-10-03

Initial beta release.

### Features
- **Asset Extraction**: Extract icon assets from Foxhole PAK files
- **Template Generation**: Create resolution-specific templates with crate overlays
- **Database Building**: Compile optimized binary template databases
- **Stockpile Scanner**: Analyze screenshots to detect items and quantities
- **API Server**: FastAPI-based HTTP API for screenshot processing
- **Docker Support**: Production-ready containerization
- **OCR Integration**: Custom-trained Tesseract model for quantity detection
- **Authentication**: Bearer token authentication for API endpoints
- **Webhooks**: Push results to external services
- **CLI Tools**: Comprehensive command-line interface

### Documentation
- User guides for all CLI tools
- API usage documentation
- Docker deployment guide
- Architecture documentation
- Configuration guide
- Troubleshooting guide
- Webhook integration guide

### Testing
- Unit tests for core services
- Integration tests for API endpoints
- Test coverage >80%
- CI/CD with GitHub Actions

[Unreleased]: https://github.com/xurxogr/foxhole-stockpiles/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/xurxogr/foxhole-stockpiles/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/xurxogr/foxhole-stockpiles/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/xurxogr/foxhole-stockpiles/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/xurxogr/foxhole-stockpiles/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/xurxogr/foxhole-stockpiles/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/xurxogr/foxhole-stockpiles/releases/tag/v0.1.0
