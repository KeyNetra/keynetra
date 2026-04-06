---
title: Kubernetes and Helm
---

# Kubernetes and Helm

Kubernetes assets are under `infra/k8s/`.

The included chart is intentionally minimal and should be extended for production environments.

## Helm Chart

Location:

- `infra/k8s/helm/keynetra/`

Key files:

- `Chart.yaml`
- `values.yaml`
- `templates/deployment.yaml`

`values.yaml` currently defines image repository/tag and service port. Deployment template provides baseline single-deployment rollout.

## What To Extend Before Production

- environment variables and secret references
- readiness/liveness probes
- resource limits/requests
- rolling update strategy
- ingress and TLS
- external database/redis service wiring

## Terraform Directory

`infra/k8s/terraform/README.md` documents intended scope:

- self-hosted modules only
- no SaaS control-plane infrastructure in this repository

## Production Considerations

For production Kubernetes usage, extend chart values for:

- environment variables and secrets
- liveness/readiness probes
- resource requests/limits
- ingress/network policy
- external Postgres and Redis connectivity

## Related Pages

- [Docker Deployment](deployment-docker.md)
- [Security](security.md)
- [Environment Variables](../reference/environment-variables.md)
