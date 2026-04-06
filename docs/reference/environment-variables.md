---
title: Environment Variables
---

# Environment Variables

Runtime settings are defined in `keynetra/config/settings.py`. `.env.example` provides baseline values.

This page summarizes runtime variables and gives a production-oriented example block.

## Core Runtime

- `KEYNETRA_ENVIRONMENT`
- `KEYNETRA_DEBUG`
- `KEYNETRA_SERVICE_MODE`
- `KEYNETRA_SERVER_HOST`
- `KEYNETRA_SERVER_PORT`
- `KEYNETRA_AUTO_SEED_SAMPLE_DATA`

Purpose:

- environment mode, server bindings, routing mode, and local bootstrap behavior

## Data Stores

- `KEYNETRA_DATABASE_URL`
- `KEYNETRA_REDIS_URL`

Purpose:

- configure primary persistence (database) and optional distributed cache/event backend (Redis)

## Authentication and Security

- `KEYNETRA_API_KEYS`
- `KEYNETRA_API_KEY_HASHES`
- `KEYNETRA_JWT_SECRET`
- `KEYNETRA_JWT_ALGORITHM`
- `KEYNETRA_ADMIN_USERNAME`
- `KEYNETRA_ADMIN_PASSWORD`
- `KEYNETRA_ADMIN_TOKEN_EXPIRY_MINUTES`

Purpose:

- configure API auth methods and admin login token behavior

## CORS

- `KEYNETRA_CORS_ALLOW_ORIGINS`
- `KEYNETRA_CORS_ALLOW_ORIGIN_REGEX`
- `KEYNETRA_CORS_ALLOW_CREDENTIALS`
- `KEYNETRA_CORS_ALLOW_METHODS`
- `KEYNETRA_CORS_ALLOW_HEADERS`

Purpose:

- browser-origin controls for web clients

## Policy and Model Loading

- `KEYNETRA_POLICIES_JSON`
- `KEYNETRA_POLICY_PATHS`
- `KEYNETRA_MODEL_PATHS`

Purpose:

- configure inline policies or load policies/models from file paths

## Caching and Resilience

- `KEYNETRA_DECISION_CACHE_TTL_SECONDS`
- `KEYNETRA_SERVICE_TIMEOUT_SECONDS`
- `KEYNETRA_CRITICAL_RETRY_ATTEMPTS`
- `KEYNETRA_RESILIENCE_MODE`
- `KEYNETRA_RESILIENCE_FALLBACK_BEHAVIOR`
- `KEYNETRA_POLICY_EVENTS_CHANNEL`

Purpose:

- decision-cache tuning, service timeout/retry behavior, and policy event distribution

## Rate Limiting

- `KEYNETRA_RATE_LIMIT_PER_MINUTE`
- `KEYNETRA_RATE_LIMIT_BURST`
- `KEYNETRA_RATE_LIMIT_WINDOW_SECONDS`

Purpose:

- configure API request throttling defaults

## OTel and OIDC

- `KEYNETRA_OTEL_ENABLED`
- `KEYNETRA_OIDC_JWKS_URL`
- `KEYNETRA_OIDC_AUDIENCE`
- `KEYNETRA_OIDC_ISSUER`

## Logging

- `KEYNETRA_LOG_FORMAT` (`json` or `rich`)
- `KEYNETRA_FORCE_COLOR` (`1`/`0`)

## Docker Startup Helpers

- `KEYNETRA_RUN_MIGRATIONS`
- `KEYNETRA_STARTUP_SCREEN`
- `KEYNETRA_HOST`
- `KEYNETRA_PORT`
- `KEYNETRA_UVICORN_WORKERS`

## Example `.env`

```bash
KEYNETRA_ENVIRONMENT=production
KEYNETRA_DATABASE_URL=postgresql+psycopg://keynetra:keynetra@postgres:5432/keynetra
KEYNETRA_REDIS_URL=redis://redis:6379/0
KEYNETRA_API_KEYS=devkey
KEYNETRA_JWT_SECRET=change-me
KEYNETRA_ADMIN_USERNAME=admin
KEYNETRA_ADMIN_PASSWORD=admin123
KEYNETRA_POLICY_PATHS=./docs/examples/assets/policies
KEYNETRA_MODEL_PATHS=./docs/examples/assets/auth-model.yaml
KEYNETRA_SERVICE_MODE=all
KEYNETRA_SERVER_HOST=0.0.0.0
KEYNETRA_SERVER_PORT=8000
KEYNETRA_LOG_FORMAT=rich
KEYNETRA_FORCE_COLOR=1
```

## Related Pages

- [Configuration Files](configuration-files.md)
- [Troubleshooting](../operations/troubleshooting.md)
- [Security](../operations/security.md)
