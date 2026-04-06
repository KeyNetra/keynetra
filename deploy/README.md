# Deploy Assets

Production-ready deployment manifests are generated in this directory.

## Structure

- `deploy/docker/`: container image and compose stack
- `deploy/kubernetes/`: raw Kubernetes manifests
- `deploy/helm/keynetra/`: installable Helm chart

## Required Environment Variables

- `KEYNETRA_DATABASE_URL`: SQLAlchemy DSN
- `KEYNETRA_REDIS_URL`: Redis URL for cache and invalidation
- `KEYNETRA_API_KEYS` or `KEYNETRA_API_KEY_HASHES`
- `KEYNETRA_API_KEY_SCOPES_JSON`: role/permission scopes for API keys
- `KEYNETRA_JWT_SECRET`: non-default outside development
- `KEYNETRA_STRICT_TENANCY=true`: required for strict multi-tenant behavior

## Quick Commands

- Docker compose:
  - `docker compose -f deploy/docker/docker-compose.yml up --build`
- Kubernetes:
  - `kubectl apply -f deploy/kubernetes/`
- Helm:
  - `helm install keynetra ./deploy/helm/keynetra`
