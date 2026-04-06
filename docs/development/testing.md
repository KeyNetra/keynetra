---
title: Testing Strategy
---

# Testing Strategy

Test suite location:

- `tests/`

## Run Tests

```bash
pytest -q
pytest -q --cov=keynetra --cov-fail-under=80
```

For quick local iteration, run targeted test modules:

```bash
pytest -q tests/test_engine.py
pytest -q tests/test_api.py
```

## Coverage Areas

Current test modules validate:

- engine behavior and explainability
- API contract and route behavior
- ACL operations
- relationship indexing
- compiled policies and policy simulation
- impact analysis
- auth model parsing/validation/compile flow
- revision consistency and caching behavior
- metrics endpoint output
- admin login flow
- migration safety utilities
- release hardening checks
- headless and CLI modes

Representative files:

- `tests/test_engine.py`
- `tests/test_api.py`
- `tests/test_api_contract.py`
- `tests/test_acl.py`
- `tests/test_auth_model.py`
- `tests/test_policy_simulation.py`
- `tests/test_impact_analysis.py`
- `tests/test_metrics_endpoint.py`
- `tests/test_services_caching.py`
- `tests/test_headless_modes.py`

## Policy Test Suites

Policy-specific deterministic testing via CLI:

```bash
python -m keynetra.cli test-policy ./policy_tests.yaml
```

## CI Expectations

CI validates lint, migration application, and coverage thresholds. Match those checks locally before opening a PR.

## Related Pages

- [CLI Reference](../reference/cli-reference.md)
- [CI/CD and Release](ci-cd-release.md)
- [Contributing](contributing.md)
