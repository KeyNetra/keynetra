# Kubernetes Deploy

Manifests are in `deploy/kubernetes/`:

- `configmap.yaml`
- `secret.yaml`
- `deployment.yaml`
- `service.yaml`
- `horizontal-pod-autoscaler.yaml`
- `ingress.yaml`

## Apply

```bash
kubectl apply -f deploy/kubernetes/
```

## Notes

- Set secure values in `secret.yaml` before applying.
- `KEYNETRA_STRICT_TENANCY` defaults to `true` in this deployment.
- Probes are configured for `/health/live` and `/health/ready`.
