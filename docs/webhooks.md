# Webhook Integration

Foxhole Stockpiles can send scan results to a webhook, enabling integration with
external systems, Discord bots, databases, and more. The webhook is one of the
configurable **output handlers** — after a screenshot is captured and scanned (or
a `.sav` file is processed), the result is POSTed to your URL.

## Configuration

Webhook output is configured as a handler in the `output.handlers` list of your
`~/.fs_config`. Add a handler with `"type": "webhook"`:

```json
{
  "config_version": 10,
  "scanner": { "database_path": "/path/to/templates.h5", "capture_key": "F9" },
  "output": {
    "handlers": [
      {
        "name": "Webhook",
        "format": { "type": "json" },
        "handler": {
          "type": "webhook",
          "url": "https://api.example.com/stockpiles"
        }
      }
    ]
  }
}
```

You can configure multiple handlers (e.g. console + webhook); each receives the
same result.

### Webhook authentication

Set `auth_type` and `token` on the webhook handler:

#### Bearer token
```json
"handler": {
  "type": "webhook",
  "url": "https://api.example.com/stockpiles",
  "auth_type": "bearer",
  "token": "your-webhook-token"
}
```
Sends: `Authorization: Bearer your-webhook-token`

#### Basic authentication
The `token` must be the base64 encoding of `username:password`
(`echo -n "user:pass" | base64`).
```json
"handler": {
  "type": "webhook",
  "url": "https://api.example.com/stockpiles",
  "auth_type": "basic",
  "token": "dXNlcjpwYXNz"
}
```
Sends: `Authorization: Basic dXNlcjpwYXNz`

#### Custom header authentication
Use `auth_type: "header"` to send the configured `token` as the value of a
header you choose via `auth_header` (e.g. an `X-API-Key`).
```json
"handler": {
  "type": "webhook",
  "url": "https://api.example.com/stockpiles",
  "auth_type": "header",
  "auth_header": "X-API-Key",
  "token": "your-webhook-token"
}
```
Sends: `X-API-Key: your-webhook-token`

## Webhook payload

**Method:** `POST`  **Content-Type:** `application/json`

```json
{
  "name": "Logi",
  "type": "Seaport",
  "shard": "ABLE",
  "ingame_timestamp": "Day 1,293, 1906 Hours",
  "timestamp": "2024-01-04T09:00:00",
  "resolution": "1920x1080",
  "items": [
    { "code": "GrenadeLauncherC", "quantity": 3, "crated": false, "confidence": 0.95 },
    { "code": "RifleW", "quantity": 120, "crated": true, "confidence": 0.92 }
  ]
}
```

`.sav`-sourced results additionally include `hex`, `coords`, and `is_reserve`
and omit per-item `x`/`y` pixel coordinates.

### Expected response

Your endpoint should return JSON. The scanner logs the response but does **not**
retry on HTTP errors.

```json
{ "message": "Stockpile received successfully" }
```

## Retry behavior

The webhook connector retries only on **connection timeouts**:
- Max retries: 3
- Delay between retries: 2 seconds
- Does **not** retry on HTTP 4xx/5xx responses.

## Testing webhooks

Point the webhook URL at a request inspector and run a scan:

- [webhook.site](https://webhook.site/) — copy your unique URL into `handler.url`.
- [RequestBin](https://requestbin.com/) — same idea.
- `nc -l 5000` and set `"url": "http://localhost:5000"` for a raw local listener.

Tip: configure a `console` handler alongside the webhook to confirm items were
detected before debugging delivery.

## Debugging

Enable debug logging to see webhook request/response details:

```json
"logging": {
  "log_level": "DEBUG",
  "loggers": { "foxhole_stockpiles.connectors.webhook": "DEBUG" }
}
```

Logs include the URL called, redacted auth headers, response status/body, and
retry attempts.

## Common issues

### Webhook returns 401 Unauthorized
Verify `auth_type`/`token` match what your endpoint expects, then test manually:
```bash
curl -X POST https://your-webhook.example.com \
  -H "Authorization: Bearer your-webhook-token" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### Connection timeout errors
- Verify the URL is reachable and the endpoint is up.
- Check firewall/network settings.

### Webhook receives empty data
Make sure the scan detected items — add a `console` handler and re-run.

## Security considerations

1. **Use HTTPS** for webhook URLs.
2. **Authenticate** with `auth_type` + `token`.
3. **Validate** auth on your endpoint.
4. Never commit tokens to version control.

## See also

- [Configuration](configuration.md) — all configuration options
- [Troubleshooting](troubleshooting.md) — capture, scanning, and output issues
