# Observability

KeyNetra emits metrics, structured logs, and audit records for authorization decisions.

## Metrics

Prometheus endpoint:

```bash
curl -i http://127.0.0.1:8080/metrics
```

Observed categories include:

- HTTP latency and request totals
- authorization decision and stage latency
- cache hit/miss behavior
- backend timeout events

## Logging

KeyNetra configures structured JSON logging in the API runtime.

Authorization-related logs include:

- auth failures
- cache get/set failures
- resilience fallback events
- audit write failures

## Dashboards

- Prometheus config: `monitoring/prometheus/prometheus.yml`
- Grafana dashboard: `monitoring/grafana/dashboards/keynetra-overview.json`

## Health Endpoints

- `/health`
- `/health/ready`

Use `/health/ready` for readiness gates in orchestration systems.
