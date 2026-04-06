---
title: Observability
---

# Observability

KeyNetra includes first-party metrics and structured logging for operational visibility.

Observability components:

- Metrics definitions: `keynetra/observability/metrics.py`
- Metrics endpoint: `keynetra/api/routes/metrics.py`
- Logging config: `keynetra/infrastructure/logging.py`
- Request logging middleware: `keynetra/api/middleware/logging.py`

## Metrics Endpoint

`GET /metrics` returns Prometheus text format (`text/plain; version=0.0.4`).

## Metric Families

From implementation, key metrics include:

- `keynetra_access_checks_total`
- `keynetra_acl_matches_total`
- `keynetra_policy_evaluations_total`
- `keynetra_relationship_traversals_total`
- `keynetra_policy_compilations_total`
- `keynetra_revision_updates_total`
- `keynetra_access_check_latency_seconds`
- `keynetra_decision_latency_seconds`
- `keynetra_cache_hits_total`
- `keynetra_cache_misses_total`
- `keynetra_cache_events_total`
- `keynetra_api_errors_total`

These metrics cover authorization decisions, cache behavior, policy/model lifecycle, and API error rates.

## Logging Modes

- JSON logs by default
- Rich colored logs when `KEYNETRA_LOG_FORMAT=rich`

Docker startup script sets rich mode by default.

Use JSON mode for log aggregation pipelines and rich mode for local operator readability.

## Prometheus and Grafana

Compose stack includes monitoring:

- Prometheus config: `infra/docker/monitoring/prometheus/prometheus.yml`
- Grafana provisioning: `infra/docker/monitoring/grafana/provisioning/`
- Dashboards: `infra/docker/monitoring/grafana/dashboards/`

## Quick Validation

```bash
curl -s http://localhost:8000/metrics | head
```

## Related Pages

- [Docker Deployment](deployment-docker.md)
- [Troubleshooting](troubleshooting.md)
- [API Reference](../reference/api-reference.md)
