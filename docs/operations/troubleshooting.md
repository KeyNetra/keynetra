---
title: Troubleshooting
---

# Troubleshooting

Use this page for common local and container runtime issues.

## Server Starts Then Exits in Docker

Check:

- `KEYNETRA_DATABASE_URL` connectivity
- migration failures in `infra/docker/start.sh`
- worker count and Uvicorn startup logs

Commands:

```bash
docker compose logs keynetra --tail=200
docker compose ps
```

Also verify `KEYNETRA_UVICORN_WORKERS`; high values can fail in constrained environments.

## No Colors in Logs

Set:

- `KEYNETRA_LOG_FORMAT=rich`
- `KEYNETRA_FORCE_COLOR=1`

For Docker, confirm env values are set in compose service environment.

If output is piped to a non-TTY, some terminals may suppress ANSI colors.

## Startup Screen Not Visible

Startup banner rendering is in `infra/docker/start.sh` and can be disabled with `KEYNETRA_STARTUP_SCREEN=0`.

## Auth Failures

Verify:

- `KEYNETRA_API_KEYS` or `KEYNETRA_API_KEY_HASHES`
- JWT secret/algorithm match
- admin credentials (`KEYNETRA_ADMIN_USERNAME`, `KEYNETRA_ADMIN_PASSWORD`)

For API-key authentication, ensure the header name is exactly `X-API-Key`.

## Migration Failures

Run manually:

```bash
python -m keynetra.cli migrate --confirm-destructive
```

Review:

- `alembic/env.py`
- `alembic/versions/`

## Config File Not Applied

Confirm command includes:

```bash
python -m keynetra.cli serve --config ./keynetra.yaml
```

Supported file types are YAML/JSON/TOML only.

If CLI still uses old values, verify no conflicting `KEYNETRA_*` variables are exported in your shell.

## Metrics Endpoint Not Available

Verify that service mode includes observability routes and check:

```bash
curl -i http://localhost:8000/metrics
```

## Related Pages

- [Docker Deployment](deployment-docker.md)
- [Configuration Files](../reference/configuration-files.md)
- [Observability](observability.md)
