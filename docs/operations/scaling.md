# Scaling

KeyNetra is designed for high-frequency authorization checks.

## Horizontal Scaling

Use multiple API replicas behind a load balancer.

Recommended production pattern:

- PostgreSQL for shared state
- Redis for distributed cache coordination
- multiple KeyNetra replicas
- Prometheus and Grafana for latency/error visibility

## What Scales Well

- stateless API replicas
- short-lived decision cache entries
- deterministic policy evaluation
- read-heavy authorization workloads

## What To Watch

- tenant-specific hot keys
- relationship fan-out for large graphs
- DB connection pool limits
- cache invalidation frequency after bulk policy changes

## Example

```bash
docker compose -f deploy/docker/docker-compose.yml up --scale keynetra=3
```

For Kubernetes, use the provided HPA in the chart or manifests.
