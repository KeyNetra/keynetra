---
title: Docker Deployment
---

# Docker Deployment

This page covers the Docker deployment assets shipped in this repository.

Docker assets:

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `infra/docker/start.sh`

## Default Stack

```bash
docker compose up --build
```

Services:

- `keynetra` API
- PostgreSQL
- Redis
- Prometheus
- Grafana

Default exposed ports:

- API: `8000`
- Postgres: `5432`
- Redis: `6379`
- Prometheus: `9090`
- Grafana: `3000`

## Development Stack

```bash
docker compose -f docker-compose.dev.yml up --build
```

Includes source mount and Uvicorn reload.

Use this stack for iterative local development when you need auto-reload behavior.

## Startup Behavior

Container entrypoint script:

1. Runs Alembic migrations if `KEYNETRA_RUN_MIGRATIONS=1`
2. Renders startup dashboard when enabled
3. Exports rich logging defaults
4. Starts Uvicorn workers

Implementation: `infra/docker/start.sh`

## Useful Environment Values

- `KEYNETRA_DATABASE_URL`
- `KEYNETRA_REDIS_URL`
- `KEYNETRA_API_KEYS`
- `KEYNETRA_ADMIN_USERNAME`
- `KEYNETRA_ADMIN_PASSWORD`
- `KEYNETRA_UVICORN_WORKERS`
- `KEYNETRA_LOG_FORMAT=rich`
- `KEYNETRA_FORCE_COLOR=1`

Example override:

```bash
KEYNETRA_API_KEYS=devkey KEYNETRA_AUTO_SEED_SAMPLE_DATA=1 docker compose up --build
```

## Health Endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

## Related Pages

- [Observability](observability.md)
- [Troubleshooting](troubleshooting.md)
- [Configuration Files](../reference/configuration-files.md)
