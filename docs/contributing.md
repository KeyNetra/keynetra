# Contributing

Start with the repository root `CONTRIBUTING.md` for contribution policy and workflow expectations.

## Local Verification

```bash
ruff check .
black --check .
isort --check-only .
mypy keynetra
pytest --cov=keynetra --cov-report=term-missing
bandit -r keynetra
detect-secrets-hook --baseline .secrets.baseline
python3.12 -m pip_audit -r requirements.lock -r requirements-dev.lock
```

## Documentation Contributions

When updating docs:

- verify commands against the real CLI
- regenerate OpenAPI if route behavior changes
- keep deployment examples aligned with `deploy/`

## Release Hygiene

- update contracts when API behavior changes
- keep tests above the coverage floor
- keep package metadata buildable with `python -m build --no-isolation`
