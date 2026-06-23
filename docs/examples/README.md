# Configuration Examples

Example `~/.fs_config` files for common setups.

## Quick Start

1. **Copy an example** to `~/.fs_config`:
   ```bash
   cp docs/examples/fs_config.minimal ~/.fs_config
   ```

2. **Edit it** for your setup:
   - Set `scanner.database_path` to your template database (`.h5`).
   - Set `scanner.capture_key` to the global hotkey you want (e.g. `"F9"`).
   - Configure output handlers (console / file / webhook / Google Sheets).

3. **Run the app** — older config files are migrated to the latest schema (v13)
   automatically the first time settings load; no manual step is needed.

## Available Examples

### `fs_config.minimal` — Bare Minimum

**Use when:** you just want to scan with defaults.

```json
{
  "config_version": 13,
  "scanner": {
    "database_path": "/app/data/foxhole_templates.h5"
  }
}
```

Add `"capture_key": "F9"` under `scanner` to enable the capture hotkey.

### `fs_config.production` — Full Setup

**Use when:** you want capture + multiple outputs + rotating logs.

**Includes:**
- ✅ Capture hotkey (`scanner.capture_key`)
- ✅ Console + Webhook output handlers (webhook with bearer auth)
- ✅ Rotating file logging at INFO level

**Required changes:**
1. Set `scanner.database_path` to your template DB.
2. Replace `your-webhook-secret-token-here` with your webhook token (or remove
   the webhook handler).
3. Update `webhook.url` with your endpoint.

**Security note:** never commit real tokens; prefer environment variables for
secrets (see below).

## Configuration Priority

Settings resolve highest → lowest:

1. **Environment variables** (`FS_*`)
2. **Configuration file** (`~/.fs_config`)
3. **Defaults**

## Using Environment Variables

Override any setting with `FS_<SECTION>__<KEY>` (double underscore between
section and key):

```bash
# Database path and capture hotkey
export FS_SCANNER__DATABASE_PATH=/custom/path/database.h5
export FS_SCANNER__CAPTURE_KEY=F9

# Logging
export FS_LOGGING__LOG_LEVEL=DEBUG
```

(Output handlers are a structured list — configure them in the JSON config file
rather than via environment variables.)

## Common Issues

### "Database not found"
- Ensure `scanner.database_path` points to an existing `.h5` file.
- Build one with `fs-tools` (see the main README) or `build_database.sh`.

### Capture does nothing
- Set `scanner.capture_key`, make sure Foxhole is running, and that its window
  is the **active**, non-minimized window when you press the hotkey.

## Full Configuration Reference

See the [Configuration Guide](../configuration.md) for all settings.

## Need Help?

- **Documentation:** [docs/](../)
- **Troubleshooting:** [docs/troubleshooting.md](../troubleshooting.md)
- **Issues:** https://github.com/xurxogr/foxhole-stockpiles/issues
