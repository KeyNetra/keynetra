# Scenario Load Tests

Scenario-driven Locust profiles for KeyNetra performance smoke checks.

## Scenarios

- `rbac_heavy_locust.py`: role/permission dominated checks
- `rebac_graph_locust.py`: relationship-heavy checks
- `multi_tenant_locust.py`: tenant/policy version variation
- `cache_warm_cold_locust.py`: warm and cold cache behavior

## Run

```bash
KEYNETRA_API_KEYS=devkey keynetra serve
locust -f scripts/load_tests/rbac_heavy_locust.py --host http://127.0.0.1:8000 --headless -u 25 -r 5 -t 30s
```

Use `--csv /tmp/locust` to export p95/throughput snapshots for CI gates.
