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
  --set image.tag=v0.1.2 \
  --set env.KEYNETRA_STRICT_TENANCY=true \
  --set secretEnv.KEYNETRA_DATABASE_URL=postgresql+psycopg://... \
  --set secretEnv.KEYNETRA_REDIS_URL=redis://... \
  --set secretEnv.KEYNETRA_API_KEY_HASHES=<hashes> \
  --set secretEnv.KEYNETRA_JWT_SECRET=<secret>
```

`values.yaml` now keeps credentials and connection URLs in `secretEnv`; reserve `env` for non-secret flags.
