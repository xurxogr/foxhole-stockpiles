# API Authentication

The Foxhole Stockpile Scanner API supports configurable authentication to protect the `/ocr/scan_image` endpoint.

## Configuration

Authentication is configured via the `api_auth` section in your settings. Both `auth_type` and `auth_token` must be set together, or both must be `None` (disabled).

### Environment Variables

```bash
# Disable authentication (default)
FS_API_AUTH__AUTH_TYPE=
FS_API_AUTH__AUTH_TOKEN=

# Enable Bearer token authentication
FS_API_AUTH__AUTH_TYPE=bearer
FS_API_AUTH__AUTH_TOKEN=your-secret-token

# Enable Basic authentication
FS_API_AUTH__AUTH_TYPE=basic
FS_API_AUTH__AUTH_TOKEN=base64-encoded-credentials
```

### Configuration File

Add to your `~/.fs_config` file:

```json
{
  "api_auth": {
    "auth_type": "bearer",
    "auth_token": "your-secret-token"
  }
}
```

## Authentication Methods

### 1. Bearer Token

**Configuration:**
```bash
FS_API_AUTH__AUTH_TYPE=bearer
FS_API_AUTH__AUTH_TOKEN=my-secret-token-123
```

**Client Request:**
```bash
curl -X POST http://localhost:8000/ocr/scan_image \
  -H "Authorization: Bearer my-secret-token-123" \
  -F "image=@stockpile.png"
```

### 2. Basic Authentication

**Configuration:**
```bash
FS_API_AUTH__AUTH_TYPE=basic
FS_API_AUTH__AUTH_TOKEN=dXNlcjpwYXNz  # base64("user:pass")
```

**Important:** The `auth_token` MUST be base64-encoded in the format `username:password`. The token is validated at startup - invalid base64 or missing colon separator will be logged as an error.

**Client Request:**
```bash
curl -X POST http://localhost:8000/ocr/scan_image \
  -H "Authorization: Basic dXNlcjpwYXNz" \
  -F "image=@stockpile.png"
```

To generate base64 credentials:
```bash
echo -n "username:password" | base64
```

> Only `bearer` and `basic` are valid for the API. `auth_type` accepts
> `basic`/`bearer`/`forward`, but `forward` is rejected for API auth by the
> settings validator.

## Disabling Authentication

To disable authentication (default behavior):

```bash
# Unset or set to empty
unset FS_API_AUTH__AUTH_TYPE
unset FS_API_AUTH__AUTH_TOKEN
```

Or in configuration file:
```json
{
  "api_auth": {
    "auth_type": null,
    "auth_token": null
  }
}
```

## Error Responses

### 401 Unauthorized - Missing Authentication
```json
{
  "detail": "Authentication required"
}
```

### 401 Unauthorized - Invalid Credentials
```json
{
  "detail": "Invalid authentication credentials"
}
```

## Notes

- The `/health` and `/` endpoints are **not** protected by authentication
- Only the `/ocr/scan_image` endpoint requires authentication when enabled
- Authentication is validated before any image processing occurs
- If `auth_type` is `None`, all requests are allowed regardless of headers
