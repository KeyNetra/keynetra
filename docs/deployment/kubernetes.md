# Kubernetes Deployment

Raw manifests are available in `deploy/kubernetes/`.

## Apply

```bash
kubectl apply -f deploy/kubernetes/
```

## Included Resources

- Deployment
- Service
- ConfigMap
- Secret
- Ingress
- HPA
- PDB
- ServiceAccount
- NetworkPolicy

## Operational Notes

- keep connection strings and secrets in `secret.yaml` or an external secret manager
- keep non-secret flags in `configmap.yaml`
- probes use `/health/live` and `/health/ready`
- strict tenancy is enabled by default in the provided deployment assets
