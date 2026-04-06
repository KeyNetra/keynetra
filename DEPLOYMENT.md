# Deployment Guide

This guide documents supported deployment paths for KeyNetra v0.1.0-beta.

## Prerequisites

- Python 3.11+
- Container runtime (Docker or compatible)
- PostgreSQL 16+ (recommended for production)
- Redis 7+ (recommended for distributed cache invalidation)

## Environment Variables

Minimum required variables:

- `KEYNETRA_DATABASE_URL`
- `KEYNETRA_API_KEYS` or `KEYNETRA_API_KEY_HASHES`
- `KEYNETRA_JWT_SECRET`
- `KEYNETRA_STRICT_TENANCY=true` (recommended for multi-tenant production)

Optional:

- `KEYNETRA_REDIS_URL`
- `KEYNETRA_RATE_LIMIT_PER_MINUTE`
- `KEYNETRA_RATE_LIMIT_BURST`
- `KEYNETRA_RUN_MIGRATIONS`
- `KEYNETRA_AUTO_SEED_SAMPLE_DATA`

See [.env.example](./.env.example) for a complete list.

## Docker (Single Container)

```bash
docker build -t keynetra:test .
docker run --rm -p 8080:8080 --env-file .env keynetra:test
```

Health and observability endpoints:

- `GET http://localhost:8080/health`
- `GET http://localhost:8080/docs`
- `GET http://localhost:8080/metrics`

## Docker Compose (Full Stack)

```bash
docker compose up --build
```

Services:

- KeyNetra API
- PostgreSQL
- Redis
- Prometheus
- Grafana
- node-exporter
- Loki

## Kubernetes Manifests

```bash
kubectl apply -f deploy/kubernetes/
```

Included resources:

- `deployment.yaml`
- `service.yaml`
- `configmap.yaml`
- `secret.yaml`
- `ingress.yaml`
- `hpa.yaml`

## Helm

```bash
helm install keynetra ./deploy/helm/keynetra
```

Render-only validation:

```bash
helm template keynetra deploy/helm/keynetra
```
