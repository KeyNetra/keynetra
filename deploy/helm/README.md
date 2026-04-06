# Helm Deploy

Chart path:

- `deploy/helm/keynetra`

## Install

```bash
helm upgrade --install keynetra ./deploy/helm/keynetra
```

## Override Examples

```bash
helm upgrade --install keynetra ./deploy/helm/keynetra \
  --set image.repository=ghcr.io/keynetra/keynetra \
  --set image.tag=v0.1.0 \
  --set env.KEYNETRA_DATABASE_URL=postgresql+psycopg://... \
  --set env.KEYNETRA_REDIS_URL=redis://... \
  --set env.KEYNETRA_STRICT_TENANCY=true \
  --set secretEnv.KEYNETRA_API_KEY_HASHES=<hashes> \
  --set secretEnv.KEYNETRA_JWT_SECRET=<secret>
```
