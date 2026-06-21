# Configuration Examples

This directory contains example configuration files for different deployment scenarios.

## Quick Start

1. **Copy the appropriate example** to `~/.fs_config`:
   ```bash
   cp docs/examples/fs_config.minimal ~/.fs_config
   ```

2. **Edit the configuration** to match your setup:
   - Update database path
   - Set authentication tokens
   - Configure webhook URLs
   - Adjust paths for your environment

3. **Run the app** — older config files are migrated to the latest format
   automatically the first time settings are loaded; no manual step is needed.

## Available Examples

### `fs_config.minimal` - Bare Minimum

**Use when:** You just want to run the scanner with default settings.

**Includes:**
- ✅ Database path only
- Default values for everything else

**Example:**
```json
{
  "config_version": 9,
  "scanner": {
    "database_path": "/app/data/foxhole_templates.h5"
  }
}
```

### `fs_config.docker` - Docker Deployment

**Use when:** Running the application in Docker containers.

**Includes:**
- ✅ Docker-friendly paths (`/app/data`, `/app/logs`, etc.)
- ✅ CORS enabled for all origins (`["*"]`) - for development only, restrict in production
- ✅ Server binds to `0.0.0.0` (listens on all container interfaces - required for Docker networking)
- ✅ Screenshot saving enabled
- ✅ File logging to persistent volume

**Security note:** The default CORS setting `["*"]` allows any origin. For production Docker deployments, use `fs_config.production` instead or update CORS to specific domains.

**Paths:**
- Database: `/app/data/foxhole_templates.h5`
- Tessdata: `/app/tessdata`
- Screenshots: `/app/screenshots`
- Logs: `/app/logs/foxhole-scanner.log`

**Docker Compose volumes:**
```yaml
volumes:
  - ./data:/app/data:ro
  - ./tessdata:/app/tessdata:ro
  - ./screenshots:/app/screenshots
  - ./logs:/app/logs
```

### `fs_config.production` - Production Setup

**Use when:** Deploying to production with security and monitoring.

**Includes:**
- ✅ **Security:** Bearer token authentication for API
- ✅ **CORS:** Restricted to specific domains
- ✅ **Webhook:** Send results to external API
- ✅ **Logging:** Rotating logs with INFO level
- ✅ **Performance:** 4 workers for high throughput
- ✅ **Monitoring:** Separate log levels for different components

**Required changes:**
1. Replace `your-secret-api-token-here` with actual API token
2. Replace `your-webhook-secret-token-here` with actual webhook token
3. Update `cors_allow_origins` with your domains
4. Update `webhook.url` with your webhook endpoint

**Security notes:**
- Never commit tokens to version control
- Use environment variables for secrets in production
- Rotate tokens regularly

## Configuration Priority

Settings are resolved in this order (highest to lowest):

1. **Environment variables** (`FS_*`) - Highest priority
2. **Configuration file** (`~/.fs_config`)
3. **Default values** - Lowest priority

## Using Environment Variables

You can override any config setting with environment variables:

```bash
# Override database path
export FS_SCANNER__DATABASE_PATH=/custom/path/database.h5

# Override API auth
export FS_API_AUTH__AUTH_TYPE=bearer
export FS_API_AUTH__AUTH_TOKEN=my-token

# Override webhook URL
export FS_OUTPUT__DESTINATION=webhook
export FS_OUTPUT__WEBHOOK__URL=https://api.example.com/hook
```

## Docker-Specific Setup

### With config file (recommended):

```bash
# 1. Copy example config
cp docs/examples/fs_config.docker .fs_config

# 2. Edit paths and settings
nano .fs_config

# 3. Run Docker Compose
docker compose up -d
```

### With environment variables only:

**Note:** Docker Compose automatically loads `.env` file if present in the same directory.

```bash
# Create .env file (Docker Compose loads this automatically)
cat > .env << EOF
FS_SCANNER__DATABASE_PATH=/app/data/foxhole_templates.h5
FS_API_AUTH__AUTH_TYPE=bearer
FS_API_AUTH__AUTH_TOKEN=my-secret-token
EOF

# Run Docker Compose (automatically uses .env)
docker compose up -d
```

**Or set variables directly:**
```bash
FS_API_AUTH__AUTH_TOKEN=my-token docker compose up -d
```

### Verify Docker configuration:

```bash
# Check health from inside container
docker compose exec api curl http://localhost:8000/health

# Check health from host (if port is mapped in docker-compose.yml)
# With ports: "127.0.0.1:8000:8000"
curl http://localhost:8000/health

# View logs
docker compose logs -f api
```

**Access from host:**
- With `ports: "127.0.0.1:8000:8000"` → Access at `http://localhost:8000`
- With `expose: 8000` only → Not accessible from host (Docker network only)
- Container always binds to `0.0.0.0:8000` internally

## Common Issues

### "Database not found"
- Ensure database path in config matches Docker volume mount
- For Docker: Use `/app/data/foxhole_templates.h5` not `/data/...`
- Check file exists: `docker compose exec api ls -la /app/data/`

### "Permission denied" on logs/screenshots
- Ensure Docker volumes have write permissions
- Check container user can write to mounted directories

### Authentication not working
- Verify `auth_type` and `auth_token` are both set
- For Docker: Ensure `.fs_config` is mounted correctly
- Test: `curl -H "Authorization: Bearer your-token" http://localhost:8000/health`

## Full Configuration Reference

See [Configuration Guide](../configuration.md) for complete documentation of all settings.

## Need Help?

- **Documentation:** [docs/](../)
- **Troubleshooting:** [docs/troubleshooting.md](../troubleshooting.md)
- **Issues:** https://github.com/yourrepo/foxhole-stockpiles/issues
