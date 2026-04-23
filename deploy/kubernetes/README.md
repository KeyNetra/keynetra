# Kubernetes Deploy

Manifests are in `deploy/kubernetes/`:

- `configmap.yaml`
- `secret.yaml`
- `deployment.yaml`
- `service.yaml`
- `hpa.yaml`
- `ingress.yaml`
- `serviceaccount.yaml`
- `pdb.yaml`
- `networkpolicy.yaml`

## Apply

```bash
kubectl apply -f deploy/kubernetes/
```

## Notes

- Keep only non-secret runtime flags in `configmap.yaml`.
- Put `KEYNETRA_DATABASE_URL`, `KEYNETRA_REDIS_URL`, API key hashes, and JWT secrets in `secret.yaml` or an external secret manager.
- `KEYNETRA_STRICT_TENANCY` defaults to `true` in this deployment.
- Unknown tenant headers now fail with `404` instead of creating tenants implicitly.
- Schedule `keynetra purge-idempotency` as a CronJob if you retain API idempotency records.
- Probes are configured for `/health/live` and `/health/ready`.
