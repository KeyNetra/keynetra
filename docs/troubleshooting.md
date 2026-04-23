# Troubleshooting

## `tenant not found`

Cause:

- request uses `X-Tenant-Id` for a tenant that does not exist

Fix:

- use the default development tenant
- create the tenant through the management API
- disable strict tenancy only for development scenarios

## `invalid api key`

Cause:

- key is missing from `KEYNETRA_API_KEYS`
- key hash or scopes are not configured

Fix:

```bash
export KEYNETRA_API_KEYS=devkey
export KEYNETRA_API_KEY_SCOPES_JSON='{"devkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
```

## OpenAPI Drift

```bash
keynetra generate-openapi --output docs/openapi.json
keynetra check-openapi --contract docs/openapi.json
```

## Redis Unavailable

Behavior:

- KeyNetra still runs without Redis
- local bounded caches continue to serve hot authorization checks

Fix:

- confirm `KEYNETRA_REDIS_URL`
- confirm network access to Redis
- inspect `/health/ready`

## Slow Authorization

Check:

- relationship graph size
- cache hit rates
- DB latency
- whether requests are forcing fully consistent mode

Use:

```bash
keynetra benchmark --api-key devkey
```
