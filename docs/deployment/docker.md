# Docker Deployment

## Build

```bash
docker build -t keynetra:test .
```

## Run

```bash
docker run --rm \
  -p 8080:8080 \
  -e KEYNETRA_DATABASE_URL=sqlite+pysqlite:////tmp/keynetra.db \
  -e KEYNETRA_API_KEYS=devkey \
  -e KEYNETRA_API_KEY_SCOPES_JSON='{"devkey":{"tenant":"default","role":"admin","permissions":["*"]}}' \
  -e KEYNETRA_RATE_LIMIT_DISABLED=true \
  keynetra:test
```

## Verify

```bash
curl -i http://127.0.0.1:8080/health/ready
```

## Image Notes

- base image: `python:3.11-slim`
- runtime user: non-root `appuser`
- baked-in healthcheck: `/health/ready`

## Compose

```bash
docker compose -f deploy/docker/docker-compose.yml up --build
```

This is appropriate for local integration and observability testing.
