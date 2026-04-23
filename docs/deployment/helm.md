# Helm Deployment

Chart path: `deploy/helm/keynetra`

## Lint And Render

```bash
helm lint deploy/helm/keynetra
helm template keynetra deploy/helm/keynetra
```

## Install

```bash
helm upgrade --install keynetra ./deploy/helm/keynetra
```

## Override Example

```bash
helm upgrade --install keynetra ./deploy/helm/keynetra \
  --set image.repository=ghcr.io/keynetra/keynetra \
  --set image.tag=v0.1.2 \
  --set env.KEYNETRA_STRICT_TENANCY=true \
  --set secretEnv.KEYNETRA_DATABASE_URL=postgresql+psycopg://keynetra:keynetra@postgres:5432/keynetra \
  --set secretEnv.KEYNETRA_REDIS_URL=redis://redis:6379/0 \
  --set secretEnv.KEYNETRA_API_KEY_HASHES=<sha256-hashes> \
  --set secretEnv.KEYNETRA_JWT_SECRET=<secret>
```

## Chart Defaults

- non-root pod security context
- read-only root filesystem
- startup, readiness, and liveness probes
- optional ingress and HPA
- secret-backed runtime credentials
